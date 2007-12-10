# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Library General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 59 Temple Place - Suite 330, Boston, MA 02111-1307, USA.
#
# See the COPYING file for license information.
#
# Copyright (c) 2006, 2007 Guillaume Chazarain <guichaz@yahoo.fr>

import asyncore
import errno
import os
import readline # Just to say we want to use it with raw_input
import signal
import socket
import subprocess
import sys
import tempfile
from threading import Thread, Event, Lock

from gsh import dispatchers, remote_dispatcher
from gsh.console import console_output, set_last_status_length

class input_buffer(object):
    """The shared input buffer between the main thread and the stdin thread"""
    def __init__(self):
        self.lock = Lock()
        self.buf = ''

    def add(self, data):
        """Add data to the buffer"""
        self.lock.acquire()
        try:
            self.buf += data
        finally:
            self.lock.release()

    def get(self):
        """Get the content of the buffer"""
        self.lock.acquire()
        try:
            data = self.buf
            if data:
                self.buf = ''
                return data
        finally:
            self.lock.release()

def ignore_sigchld(ignore):
    """Typically we don't want to create zombie. But when executing a user
    command (!command) the subprocess module relies on zombies not being
    automatically reclaimed"""
    if ignore:
        signal.signal(signal.SIGCHLD, signal.SIG_IGN)
        # Reclaim previously created zombies
        try:
            while os.waitpid(-1, os.WNOHANG) != (0, 0):
                pass
        except OSError, e:
            if e.errno != errno.ECHILD:
                raise
    else:
        signal.signal(signal.SIGCHLD, signal.SIG_DFL)

def process_input_buffer():
    """Send the content of the input buffer to all remote processes, this must
    be called in the main thread"""
    from gsh.control_commands_helpers import handle_control_command
    data = the_stdin_thread.input_buffer.get()
    if not data:
        return

    if data.startswith(':'):
        handle_control_command(data[1:-1])
        return

    if data.startswith('!'):
        ignore_sigchld(False)
        retcode = subprocess.call(data[1:], shell=True)
        ignore_sigchld(True)
        if retcode > 0:
            console_output('Child returned %d\n' % retcode)
        elif retcode < 0:
            console_output('Child was terminated by signal %d\n' % -retcode)
        return

    for r in dispatchers.all_instances():
        try:
            r.dispatch_write(data)
        except asyncore.ExitNow, e:
            raise e
        except Exception, msg:
            console_output('%s for %s, disconnecting\n' % (msg, r.display_name))
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

class socket_notification_reader(asyncore.dispatcher):
    """The socket reader in the main thread"""
    def __init__(self):
        asyncore.dispatcher.__init__(self, the_stdin_thread.socket_read)

    def _do(self, c):
        if c == 'd':
            process_input_buffer()
        else:
            raise Exception, 'Unknown code: %s' % (c)

    def handle_read(self):
        """Handle all the available character commands in the socket"""
        while True:
            try:
                c = self.recv(1)
            except socket.error, why:
                assert why[0] == errno.EWOULDBLOCK
                return
            else:
                self._do(c)
                self.socket.setblocking(True)
                self.send('A')
                self.socket.setblocking(False)

    def writable(self):
        """Our writes are blocking"""
        return False

# All the words that have been typed in gsh. Used by the completion mechanism.
history_words = set()

# When listing possible completions, the complete() function is called with
# an increasing state parameter until it returns None. Cache the completion
# list instead of regenerating it for each completion item.
completion_results = None

def complete(text, state):
    """On tab press, return the next possible completion"""
    from gsh.control_commands_helpers import complete_control_command
    global completion_results
    if state == 0:
        line = readline.get_line_buffer()
        if line.startswith(':'):
            # Control command completion
            completion_results = complete_control_command(line, text)
        else:
            # Main shell completion from history
            l = len(text)
            completion_results = [w + ' ' for w in history_words if len(w) > l \
                                                         and w.startswith(text)]
    if state < len(completion_results):
        return completion_results[state]
    completion_results = None

def write_main_socket(c):
    """Synchronous write to the main socket, wait for ACK"""
    the_stdin_thread.socket_write.send(c)
    while True:
        try:
            the_stdin_thread.socket_write.recv(1)
        except socket.error, e:
            assert e[0] == errno.EINTR
        else:
            break

#
# This file descriptor is used to interrupt readline in raw_input().
# /dev/null is not enough as it does not get out of a 'Ctrl-R' reverse-i-search.
# A Ctrl-C seems to make raw_input() return in all cases, and avoids printing
# a newline
tempfile_fd, tempfile_name = tempfile.mkstemp()
os.remove(tempfile_name)
os.write(tempfile_fd, chr(3))

def get_stdin_pid(cached_result=None):
    '''Try to get the PID of the stdin thread, otherwise get the whole process
    ID'''
    if cached_result is None:
        try:
            tasks = os.listdir('/proc/self/task')
        except OSError, e:
            if e.errno != errno.ENOENT:
                raise
            cached_result = os.getpid()
        else:
            tasks.remove(str(os.getpid()))
            assert len(tasks) == 1
            cached_result = int(tasks[0])
    return cached_result

def interrupt_stdin_thread():
    """The stdin thread may be in raw_input(), get out of it"""
    dupped_stdin = os.dup(0) # Backup the stdin fd
    assert not the_stdin_thread.interrupt_asked # Sanity check
    the_stdin_thread.interrupt_asked = True # Not user triggered
    os.lseek(tempfile_fd, 0, 0) # Rewind in the temp file
    os.dup2(tempfile_fd, 0) # This will make raw_input() return
    pid = get_stdin_pid()
    os.kill(pid, signal.SIGWINCH) # Try harder to wake up raw_input()
    the_stdin_thread.out_of_raw_input.wait() # Wait for this return
    the_stdin_thread.interrupt_asked = False # Restore sanity
    os.dup2(dupped_stdin, 0) # Restore stdin
    os.close(dupped_stdin) # Cleanup


class stdin_thread(Thread):
    """The stdin thread, used to call raw_input()"""
    def __init__(self):
        Thread.__init__(self, name='stdin thread')

    @staticmethod
    def activate(interactive):
        """Activate the thread at initialization time"""
        the_stdin_thread.input_buffer = input_buffer()
        if interactive:
            the_stdin_thread.raw_input_wanted = Event()
            the_stdin_thread.in_raw_input = Event()
            the_stdin_thread.out_of_raw_input = Event()
            the_stdin_thread.out_of_raw_input.set()
            s1, s2 = socket.socketpair()
            the_stdin_thread.socket_read, the_stdin_thread.socket_write = s1, s2
            the_stdin_thread.interrupt_asked = False
            the_stdin_thread.setDaemon(True)
            the_stdin_thread.start()
            the_stdin_thread.socket_notification = socket_notification_reader()

    def want_raw_input(self):
        self.raw_input_wanted.set()
        self.socket_notification.handle_read()
        self.in_raw_input.wait()
        self.raw_input_wanted.clear()

    def no_raw_input(self):
        interrupt_stdin_thread()

    # Beware of races
    def run(self):
        while True:
            self.raw_input_wanted.wait()
            self.out_of_raw_input.set()
            readline.set_completer(complete)
            readline.parse_and_bind('tab: complete')
            readline.set_completer_delims(' \t\n')
            nr, total = dispatchers.count_awaited_processes()
            if nr:
                prompt = 'waiting (%d/%d)> ' % (nr, total)
            else:
                prompt = 'ready (%d)> ' % total
            set_last_status_length(len(prompt))
            self.in_raw_input.set()
            self.out_of_raw_input.clear()
            cmd = None
            try:
                cmd = raw_input(prompt)
            except EOFError:
                if not self.interrupt_asked:
                    cmd = ':quit'
            if self.interrupt_asked:
                cmd = None
            self.in_raw_input.clear()
            self.out_of_raw_input.set()
            if cmd is not None:
                words = [w for w in cmd.split() if len(w) > 1]
                history_words.update(words)
                if len(history_words) > 10000:
                    del history_words[:-10000]
                self.input_buffer.add(cmd + '\n')
                write_main_socket('d')

the_stdin_thread = stdin_thread()
