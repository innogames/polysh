"""Polysh - Standard Input Routines

Copyright (c) 2006 Guillaume Chazarain <guichaz@gmail.com>
Copyright (c) 2024 InnoGames GmbH
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

import atexit
import errno
import fcntl
import os
import readline  # Just to say we want to use it with raw_input
import socket
import subprocess
import sys
import termios
from threading import Event, Lock, Thread
from typing import Optional

_TRACE = os.environ.get('POLYSH_TRACE')


def _trace(msg: str) -> None:
    if _TRACE:
        print(f'[trace] {msg}', file=sys.stderr, flush=True)

from polysh import (
    completion,
    dispatcher_registry,
    dispatchers,
    remote_dispatcher,
)
from polysh.console import console_output, set_last_status_length
from polysh.exceptions import ExitNow

the_stdin_thread = None  # type: StdinThread


class InputBuffer:
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
        except UnicodeDecodeError:
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
            console_output(f'Child returned {retcode:d}\n'.encode())
        elif retcode < 0:
            console_output(
                f'Child was terminated by signal {-retcode:d}\n'.encode()
            )
        return

    for r in dispatchers.all_instances():
        try:
            r.dispatch_command(data)
        except ExitNow as e:
            raise e
        except Exception as msg:
            raise msg
            console_output(
                f'{str(msg)} for {r.display_name}, disconnecting\n'.encode()
            )
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


class SocketDispatcher:
    """Base dispatcher class for socket-based communication."""

    def __init__(self, sock: socket.socket) -> None:
        self.socket = sock
        self.fd = sock.fileno()

        # Set non-blocking mode
        flags = fcntl.fcntl(self.fd, fcntl.F_GETFL)
        fcntl.fcntl(self.fd, fcntl.F_SETFL, flags | os.O_NONBLOCK)

        # Register with the dispatcher registry
        dispatcher_registry.register(self.fd, self)

    def recv(self, buffer_size: int) -> bytes:
        """Read from the socket."""
        return self.socket.recv(buffer_size)

    def send(self, data: bytes) -> int:
        """Write to the socket."""
        return self.socket.send(data)

    def close(self) -> None:
        """Unregister and close the socket."""
        dispatcher_registry.unregister(self.fd)
        try:
            self.socket.close()
        except OSError:
            pass

    def readable(self) -> bool:
        """Override in subclass."""
        return True

    def writable(self) -> bool:
        """Override in subclass."""
        return False

    def handle_read(self) -> None:
        """Override in subclass."""
        pass

    def handle_write(self) -> None:
        """Override in subclass."""
        pass

    def handle_close(self) -> None:
        """Handle connection close."""
        self.close()


class SocketNotificationReader(SocketDispatcher):
    """The socket reader in the main thread"""

    def __init__(self, the_stdin_thread: 'StdinThread') -> None:
        super().__init__(the_stdin_thread.socket_read)

    def _do(self, c: bytes) -> None:
        _trace(f'SocketNotificationReader: got {c!r}')
        if c == b'd':
            process_input_buffer()
        else:
            raise Exception('Unknown code: %s' % (c))

    def handle_read(self) -> None:
        """Handle all the available character commands in the socket"""
        while True:
            try:
                c = self.recv(1)
            except OSError as e:
                if e.errno == errno.EWOULDBLOCK:
                    return
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
        except OSError as e:
            if e.errno != errno.EINTR:
                raise
        else:
            break


#
# Readline interrupt mechanism using a pty pair.
#
# We interpose a pty between the real terminal and readline:
#   real terminal -> [proxy thread] -> pty master -> pty slave (fd 0) -> readline
#
# To interrupt readline, we write '\n' to the pty master.  readline sees it
# as a normal Enter keypress and returns immediately.  The interrupt_asked
# flag tells the stdin thread to discard the input and save partial text.
#
# This avoids signals (Python dispatches handlers only in the main thread)
# and avoids needing access to readline internals (rl_done).
#

_pty_master_fd = None  # type: Optional[int]
_real_stdin_fd = None  # type: Optional[int]
_real_stdin_attrs = None  # original terminal settings


def _setup_stdin_pty() -> None:
    """Replace fd 0 with a pty slave and start a proxy from the real terminal.
    Must be called before the stdin thread starts and before restore_tty_on_exit."""
    global _pty_master_fd, _real_stdin_fd, _real_stdin_attrs

    _real_stdin_fd = os.dup(0)  # save the real terminal

    # Save real terminal settings for restoration on exit
    try:
        _real_stdin_attrs = termios.tcgetattr(_real_stdin_fd)
    except termios.error:
        pass

    master_fd, slave_fd = os.openpty()
    os.dup2(slave_fd, 0)  # fd 0 is now the pty slave
    os.close(slave_fd)
    _pty_master_fd = master_fd

    # Copy terminal size from real terminal to pty slave
    try:
        size = fcntl.ioctl(_real_stdin_fd, termios.TIOCGWINSZ, b'\x00' * 8)
        fcntl.ioctl(0, termios.TIOCSWINSZ, size)
    except OSError:
        pass

    # Put real terminal in cbreak mode: no echo, no line buffering, but
    # keep ISIG so Ctrl-C/Ctrl-Z still generate signals
    try:
        attrs = termios.tcgetattr(_real_stdin_fd)
        attrs[3] &= ~(termios.ECHO | termios.ICANON)  # type: ignore
        attrs[6][termios.VMIN] = 1  # type: ignore
        attrs[6][termios.VTIME] = 0  # type: ignore
        termios.tcsetattr(_real_stdin_fd, termios.TCSANOW, attrs)
    except termios.error:
        pass

    atexit.register(_restore_real_stdin)

    # Start proxy thread: real terminal -> pty master
    proxy = Thread(target=_stdin_proxy_loop, name='stdin-proxy', daemon=True)
    proxy.start()
    _trace(f'stdin pty set up: real_stdin_fd={_real_stdin_fd}, master_fd={master_fd}')


def _restore_real_stdin() -> None:
    """Restore original terminal settings on exit."""
    if _real_stdin_attrs is not None and _real_stdin_fd is not None:
        try:
            termios.tcsetattr(_real_stdin_fd, termios.TCSADRAIN, _real_stdin_attrs)
        except termios.error:
            pass


def _stdin_proxy_loop() -> None:
    """Forward bytes from the real terminal to the pty master."""
    while True:
        try:
            data = os.read(_real_stdin_fd, 4096)
            if not data:
                break
            os.write(_pty_master_fd, data)
        except OSError:
            break


def propagate_terminal_size() -> None:
    """Copy the real terminal size to the pty slave.  Call from SIGWINCH handler."""
    if _real_stdin_fd is not None and _pty_master_fd is not None:
        try:
            size = fcntl.ioctl(_real_stdin_fd, termios.TIOCGWINSZ, b'\x00' * 8)
            fcntl.ioctl(0, termios.TIOCSWINSZ, size)
        except OSError:
            pass


def interrupt_stdin_thread() -> None:
    """Interrupt readline by writing a newline to the pty master.

    readline sees Enter and returns the current buffer.  The stdin thread
    checks interrupt_asked and saves the partial input as prepend_text.
    """
    _trace('interrupt_stdin_thread: starting')
    if _pty_master_fd is None:
        _trace('interrupt_stdin_thread: no pty, cannot interrupt')
        return
    assert not the_stdin_thread.interrupt_asked
    the_stdin_thread.interrupt_asked = True
    os.write(_pty_master_fd, b'\n')

    if not the_stdin_thread.out_of_raw_input.wait(timeout=3.0):
        _trace('interrupt_stdin_thread: FAILED - stdin thread did not respond within 3s')
        the_stdin_thread.interrupt_asked = False
        return
    _trace('interrupt_stdin_thread: stdin thread responded')
    the_stdin_thread.interrupt_asked = False
    # Move cursor up to undo the newline that readline printed when it
    # processed our injected Enter.  This lets the next prompt overwrite
    # the current line in-place.
    os.write(1, b'\033[A\r')


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
        _trace(f'want_raw_input: setting raw_input_wanted, prompt={prompt!r}')
        self.raw_input_wanted.set()
        while not self.in_raw_input.is_set():
            self.socket_notification.handle_read()
            self.in_raw_input.wait(0.1)
        _trace('want_raw_input: stdin thread is in input()')
        self.raw_input_wanted.clear()

    def no_raw_input(self) -> None:
        if not self.out_of_raw_input.is_set():
            interrupt_stdin_thread()

    # Beware of races
    def run(self) -> None:
        while True:
            _trace('stdin thread: waiting for raw_input_wanted')
            self.raw_input_wanted.wait()
            _trace(f'stdin thread: entering input(), prompt={self.prompt!r}')
            self.out_of_raw_input.set()
            self.in_raw_input.set()
            self.out_of_raw_input.clear()
            cmd = None
            try:
                cmd = input(self.prompt)
                _trace(f'stdin thread: input() returned cmd={cmd!r}')
            except EOFError:
                _trace(f'stdin thread: EOFError, interrupt_asked={self.interrupt_asked}')
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
                self.input_buffer.add(f'{cmd}\n'.encode())
                write_main_socket(b'd')
