"""Polysh - Standard Input Routines

Copyright (c) 2006 Guillaume Chazarain <guichaz@gmail.com>
Copyright (c) 2018 InnoGames GmbH
"""
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 2 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

import asyncore
import errno
import os
import readline  # Just to say we want to use it with raw_input
import signal
import socket
import subprocess
import sys
import tempfile
import termios
from threading import Thread, Event, Lock

from polysh import dispatchers, remote_dispatcher
from polysh.console import console_output, set_last_status_length
from polysh import completion
from typing import Optional

the_stdin_thread = None  # type: StdinThread


class InputBuffer(object):
    """The shared input buffer between the main thread and the stdin thread"""

    def __init__(self) -> None:
        self.lock = Lock()
        self.buf = b''

    def add(self, data: bytes) -> None:
        """Add data to the buffer"""
        with self.lock:
            self.buf += data

    def get(self) -> bytes:
        """Get the content of the buffer"""
        data = b''
        with self.lock:
            data, self.buf = self.buf, b''

        return data


def process_input_buffer() -> None:
    """Send the content of the input buffer to all remote processes, this must
    be called in the main thread"""
    from polysh.control_commands_helpers import handle_control_command
    data = the_stdin_thread.input_buffer.get()
    remote_dispatcher.log(b'> ' + data)

    if data.startswith(b':'):
        try:
            handle_control_command(data[1:-1].decode())
        except UnicodeDecodeError as e:
            console_output(b'Could not decode command.')
        return

    if data.startswith(b'!'):
        try:
            retcode = subprocess.call(data[1:], shell=True)
        except OSError as e:
            if e.errno == errno.EINTR:
                console_output(b'Child was interrupted\n')
                retcode = 0
            else:
                raise
        if retcode > 128 and retcode <= 192:
            retcode = 128 - retcode
        if retcode > 0:
            console_output('Child returned {:d}\n'.format(retcode).encode())
        elif retcode < 0:
            console_output('Child was terminated by signal {:d}\n'.format(
                -retcode).encode())
        return

    for r in dispatchers.all_instances():
        try:
            r.dispatch_command(data)
        except asyncore.ExitNow as e:
            raise e
        except Exception as msg:
            raise msg
            console_output('{} for {}, disconnecting\n'.format(
                str(msg), r.display_name).encode())
            r.disconnect()
        else:
            if r.enabled and r.state is remote_dispatcher.STATE_IDLE:
                r.change_state(remote_dispatcher.STATE_RUNNING)

# The stdin thread uses a synchronous (with ACK) socket to communicate with the
# main thread, which is most of the time waiting in the poll() loop.
# Socket character protocol:
# d: there is new data to send
# A: ACK, same reply for every message, communications are synchronous, so the
# stdin thread sends a character to the socket, the main thread processes it,
# sends the ACK, and the stdin thread can go on.


class SocketNotificationReader(asyncore.dispatcher):
    """The socket reader in the main thread"""

    def __init__(self, the_stdin_thread: 'StdinThread') -> None:
        asyncore.dispatcher.__init__(self, the_stdin_thread.socket_read)

    def _do(self, c: bytes) -> None:
        if c == b'd':
            process_input_buffer()
        else:
            raise Exception('Unknown code: %s' % (c))

    def handle_read(self) -> None:
        """Handle all the available character commands in the socket"""
        while True:
            try:
                c = self.recv(1)
            except socket.error as e:
                if e.errno == errno.EWOULDBLOCK:
                    return
                else:
                    raise
            else:
                self._do(c)
                self.socket.setblocking(True)
                self.send(b'A')
                self.socket.setblocking(False)

    def writable(self) -> bool:
        """Our writes are blocking"""
        return False


def write_main_socket(c: bytes) -> None:
    """Synchronous write to the main socket, wait for ACK"""
    the_stdin_thread.socket_write.send(c)
    while True:
        try:
            the_stdin_thread.socket_write.recv(1)
        except socket.error as e:
            if e.errno != errno.EINTR:
                raise
        else:
            break


#
# This file descriptor is used to interrupt readline in raw_input().
# /dev/null is not enough as it does not get out of a 'Ctrl-R' reverse-i-search.
# A Ctrl-C seems to make raw_input() return in all cases, and avoids printing
# a newline
tempfile_fd, tempfile_name = tempfile.mkstemp()
os.remove(tempfile_name)
os.write(tempfile_fd, b'\x03')


def get_stdin_pid(cached_result: Optional[int] = None) -> int:
    """Try to get the PID of the stdin thread, otherwise get the whole process
    ID"""
    if cached_result is None:
        try:
            tasks = os.listdir('/proc/self/task')
        except OSError as e:
            if e.errno != errno.ENOENT:
                raise
            cached_result = os.getpid()
        else:
            tasks.remove(str(os.getpid()))
            assert len(tasks) == 1
            cached_result = int(tasks[0])
    return cached_result


def interrupt_stdin_thread() -> None:
    """The stdin thread may be in raw_input(), get out of it"""
    dupped_stdin = os.dup(0)  # Backup the stdin fd
    assert not the_stdin_thread.interrupt_asked  # Sanity check
    the_stdin_thread.interrupt_asked = True  # Not user triggered
    os.lseek(tempfile_fd, 0, 0)  # Rewind in the temp file
    os.dup2(tempfile_fd, 0)  # This will make raw_input() return
    pid = get_stdin_pid()
    os.kill(pid, signal.SIGWINCH)  # Try harder to wake up raw_input()
    the_stdin_thread.out_of_raw_input.wait()  # Wait for this return
    the_stdin_thread.interrupt_asked = False  # Restore sanity
    os.dup2(dupped_stdin, 0)  # Restore stdin
    os.close(dupped_stdin)  # Cleanup


echo_enabled = True


def set_echo(echo: bool) -> None:
    global echo_enabled
    if echo != echo_enabled:
        fd = sys.stdin.fileno()
        attr = termios.tcgetattr(fd)
        # The following raises a mypy warning, as python type hints don't allow
        # per list item granularity.  The last item in attr is List[bytes], but
        # we don't access that here.
        if echo:
            attr[3] |= termios.ECHO  # type: ignore
        else:
            attr[3] &= ~termios.ECHO  # type: ignore
        termios.tcsetattr(fd, termios.TCSANOW, attr)
        echo_enabled = echo


class StdinThread(Thread):
    """The stdin thread, used to call raw_input()"""

    def __init__(self, interactive: bool) -> None:
        Thread.__init__(self, name='stdin thread')
        completion.install_completion_handler()
        self.input_buffer = InputBuffer()

        if interactive:
            self.raw_input_wanted = Event()
            self.in_raw_input = Event()
            self.out_of_raw_input = Event()
            self.out_of_raw_input.set()
            s1, s2 = socket.socketpair()
            self.socket_read, self.socket_write = s1, s2
            self.interrupt_asked = False
            self.setDaemon(True)
            self.start()
            self.socket_notification = SocketNotificationReader(self)
            self.prepend_text = None  # type: Optional[str]
            readline.set_pre_input_hook(self.prepend_previous_text)

    def prepend_previous_text(self) -> None:
        if self.prepend_text:
            readline.insert_text(self.prepend_text)
            readline.redisplay()
            self.prepend_text = None

    def want_raw_input(self) -> None:
        nr, total = dispatchers.count_awaited_processes()
        if nr:
            prompt = 'waiting (%d/%d)> ' % (nr, total)
        else:
            prompt = 'ready (%d)> ' % total
        self.prompt = prompt
        set_last_status_length(len(prompt))
        self.raw_input_wanted.set()
        while not self.in_raw_input.is_set():
            self.socket_notification.handle_read()
            self.in_raw_input.wait(0.1)
        self.raw_input_wanted.clear()

    def no_raw_input(self) -> None:
        if not self.out_of_raw_input.is_set():
            interrupt_stdin_thread()

    # Beware of races
    def run(self) -> None:
        while True:
            self.raw_input_wanted.wait()
            self.out_of_raw_input.set()
            self.in_raw_input.set()
            self.out_of_raw_input.clear()
            cmd = None
            try:
                cmd = input(self.prompt)
            except EOFError:
                if self.interrupt_asked:
                    cmd = readline.get_line_buffer()
                else:
                    cmd = chr(4)  # Ctrl-D
            if self.interrupt_asked:
                self.prepend_text = cmd
                cmd = None
            self.in_raw_input.clear()
            self.out_of_raw_input.set()
            if cmd:
                if echo_enabled:
                    completion.add_to_history(cmd)
                else:
                    completion.remove_last_history_item()
            set_echo(True)
            if cmd is not None:
                self.input_buffer.add('{}\n'.format(cmd).encode())
                write_main_socket(b'd')
