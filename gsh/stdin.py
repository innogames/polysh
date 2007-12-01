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
import atexit
import errno
import fcntl
import os
import readline # Just to say we want to use it with raw_input
import socket
import sys
from threading import Thread, Event, Lock

from gsh import dispatchers, remote_dispatcher
from gsh.console import console_output, set_last_status_length

# Handling of stdin is certainly the most complex part of gsh

stdin_fcntl_flags = fcntl.fcntl(0, fcntl.F_GETFL, 0)

def set_stdin_blocking(blocking):
    """We set O_NONBLOCK on stdin only when we read from it"""
    if blocking:
        flags = stdin_fcntl_flags & ~os.O_NONBLOCK
    else:
        flags = stdin_fcntl_flags | os.O_NONBLOCK
    fcntl.fcntl(0, fcntl.F_SETFL, flags)

class stdin_dispatcher(asyncore.file_dispatcher):
    """The stdin reader in the main thread => no fancy editing"""
    def __init__(self):
        asyncore.file_dispatcher.__init__(self, 0)
        self.is_readable = True
        def restore_stdin_flags():
            try:
                fcntl.fcntl(0, fcntl.F_SETFL, stdin_fcntl_flags)
            except IOError, e:
                if e.errno != errno.EBADF:
                    # stdin may have been closed, otherwise propagate
                    raise e
        atexit.register(restore_stdin_flags)
        set_stdin_blocking(True)

    def readable(self):
        """We set it to be readable only when the stdin thread is not in
        raw_input()"""
        return self.is_readable

    def handle_expt(self):
        # Emulate the select with poll as in: asyncore.loop(use_poll=True)
        self.handle_read()

    def writable(self):
        """We don't write to stdin"""
        return False

    def handle_close(self):
        """Ctrl-D was received but the remote processes were not ready"""
        dispatchers.dispatch_termination_to_all()

    def handle_read(self):
        """Some data can be read on stdin"""
        while True:
            try:
                try:
                    set_stdin_blocking(False)
                    try:
                        data = self.recv(4096)
                    finally:
                        set_stdin_blocking(True)
                except OSError, e:
                    if e.errno == errno.EAGAIN:
                        # End of available data
                        break
                    else:
                        raise
                else:
                    if data:
                        # Handle the just read data
                        the_stdin_thread.input_buffer.add(data)
                        process_input_buffer()
                    else:
                        # Closed?
                        self.is_readable = False
                        break
            except KeyboardInterrupt:
                pass

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

def process_input_buffer():
    """Send the content of the input buffer to all remote processes, this must
    be called in the main thread"""
    from gsh.control_shell import handle_control_command
    data = the_stdin_thread.input_buffer.get()
    if not data:
        return

    if data.startswith(':'):
        handle_control_command(data[1:-1])
        return

    for r in dispatchers.all_instances():
        try:
            r.dispatch_write(data)
        except asyncore.ExitNow, e:
            raise e
        except Exception, msg:
            console_output('%s for %s, disconnecting\n' % (msg, r.display_name),
                           output=sys.stderr)
            r.disconnect()
        else:
            if r.enabled and r.state is remote_dispatcher.STATE_IDLE:
                r.change_state(remote_dispatcher.STATE_RUNNING)

# The stdin thread uses a synchronous (with ACK) socket to communicate with the
# main thread, which is most of the time waiting in the poll() loop.
# Socket character protocol:
# s: entering in raw_input, the main loop should not read stdin
# e: leaving raw_input, the main loop can read stdin
# q: Ctrl-D was pressed, exiting
# d: there is new data to send
# A: ACK, same reply for every message, communications are synchronous, so the
# stdin thread sends a character to the socket, the main thread processes it,
# sends the ACK, and the stdin thread can go on.

class socket_notification_reader(asyncore.dispatcher):
    """The socket reader in the main thread"""
    def __init__(self, the_stdin_dispatcher):
        asyncore.dispatcher.__init__(self, the_stdin_thread.socket_read)
        self.the_stdin_dispatcher = the_stdin_dispatcher

    def _do(self, c):
        if c in ('s', 'e'):
            self.the_stdin_dispatcher.is_readable = c == 'e'
            console_output('\r')
        elif c == 'q':
            dispatchers.dispatch_termination_to_all()
        elif c == 'd':
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

def complete(text, state):
    """On tab press, return the next possible completion"""
    from gsh.control_shell import complete_control_command
    if readline.get_line_buffer().startswith(':'):
        if readline.get_begidx() == 0:
            return ':' + complete_control_command(text[1:], state)
        return complete_control_command(text, state)
    l = len(text)
    matches = [w for w in history_words if len(w) > l and w.startswith(text)]
    if state <= len(matches):
        return matches[state]

def write_main_socket(c):
    """Synchronous write to the main socket, wait for ACK"""
    the_stdin_thread.socket_write.send(c)
    the_stdin_thread.socket_write.recv(1)

class stdin_thread(Thread):
    """The stdin thread, used to call raw_input()"""
    def __init__(self):
        Thread.__init__(self, name='stdin thread')

    @staticmethod
    def activate(interactive):
        """Activate the thread at initialization time"""
        the_stdin_thread.ready_event = Event()
        the_stdin_thread.input_buffer = input_buffer()
        if interactive:
            the_stdin_thread.interrupted_event = Event()
            s1, s2 = socket.socketpair()
            the_stdin_thread.socket_read, the_stdin_thread.socket_write = s1, s2
            the_stdin_thread.wants_control_shell = False
            the_stdin_thread.setDaemon(True)
            the_stdin_thread.start()
            the_stdin_dispatcher = stdin_dispatcher()
            socket_notification_reader(the_stdin_dispatcher)
        else:
            the_stdin_thread.ready_event.set()

    def run(self):
        while True:
            while True:
                self.ready_event.wait()
                nr, total = dispatchers.count_completed_processes()
                if nr == total:
                    break
            # The remote processes are ready, the thread can call raw_input
            self.interrupted_event.clear()
            try:
                try:
                    write_main_socket('s')
                    readline.set_completer(complete)
                    readline.parse_and_bind('tab: complete')
                    readline.set_completer_delims(' \t\n')
                    prompt = 'ready (%d)> ' % (nr)
                    set_last_status_length(len(prompt))
                    cmd = raw_input(prompt)
                    if self.wants_control_shell:
                        # This seems to be needed if Ctrl-C is hit when some
                        # text is in the line buffer
                        raise EOFError
                    words = [w + ' ' for w in cmd.split() if len(w) > 1]
                    history_words.update(words)
                    if len(history_words) > 10000:
                        del history_words[:-10000]
                finally:
                    if not self.wants_control_shell:
                        write_main_socket('e')
            except EOFError:
                if self.wants_control_shell:
                    self.ready_event.clear()
                    # Ok, we are no more in raw_input(), tell it to the
                    # main thread
                    self.interrupted_event.set()
                else:
                    write_main_socket('q')
                    return
            else:
                self.ready_event.clear()
                self.input_buffer.add(cmd + '\n')
                write_main_socket('d')

the_stdin_thread = stdin_thread()
