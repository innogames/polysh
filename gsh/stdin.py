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
# Copyright (c) 2006 Guillaume Chazarain <guichaz@yahoo.fr>

import asyncore
import atexit
import errno
import fcntl
import os
import readline # Just to say we want to use it with raw_input
import sys
from threading import Thread, Event, Lock

from gsh import remote_dispatcher
from gsh.console import console_output

# Handling of stdin is certainly the most complex part of gsh

stdin_fcntl_flags = fcntl.fcntl(0, fcntl.F_GETFL, 0)

def set_stdin_blocking(blocking):
    """We set O_NONBLOCK on stdin only when we read from it"""
    if blocking:
        flags = stdin_fcntl_flags & ~os.O_NONBLOCK
    else:
        flags = stdin_fcntl_flags | os.O_NONBLOCK
    fcntl.fcntl(0, fcntl.F_SETFL, flags)

def restore_streams_flags_at_exit():
    """We play we fcntl flags, so we make sure to restore them on exit"""
    atexit.register(fcntl.fcntl, 0, fcntl.F_SETFL, stdin_fcntl_flags)

class stdin_dispatcher(asyncore.file_dispatcher):
    """The stdin reader in the main thread => no fancy editing"""
    def __init__(self):
        asyncore.file_dispatcher.__init__(self, 0)
        self.is_readable = True
        atexit.register(fcntl.fcntl, 0, fcntl.F_SETFL, stdin_fcntl_flags)
        set_stdin_blocking(True)

    def readable(self):
        """We set it to be readable only when the stdin thread is not in
        raw_input()"""
        return self.is_readable

    def writable(self):
        """We don't write to stdin"""
        return False

    def handle_close(self):
        """Ctrl-D was received but the remote processes were not ready"""
        remote_dispatcher.dispatch_termination_to_all()

    def handle_read(self):
        """Some data can be read on stdin"""
        while True:
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
    data = the_stdin_thread.input_buffer.get()
    if not data:
        return
    for r in remote_dispatcher.all_instances():
        try:
            r.dispatch_write(data)
        except Exception, msg:
            console_output('%s for %s, disconnecting\n' % (msg, r.display_name),
                           output=sys.stderr)
            r.disconnect()
        else:
            if r.is_logging():
                r.log('<== ' + data)
            if r.enabled and r.state is remote_dispatcher.STATE_IDLE:
                r.change_state(remote_dispatcher.STATE_EXPECTING_NEXT_LINE)

# The stdin thread uses a pipe to communicate with the main thread, which is
# most of the time waiting in the select() loop.
# Pipe character protocol:
# s: entering in raw_input, the main loop should not read stdin
# e: leaving raw_input, the main loop can read stdin
# q: Ctrl-D was pressed, exiting
# d: there is new data to send

class pipe_notification_reader(asyncore.file_dispatcher):
    """The pipe reader in the main thread"""
    def __init__(self):
        asyncore.file_dispatcher.__init__(self, the_stdin_thread.pipe_read)

    def _do(self, c):
        if c in ('s', 'e'):
            the_stdin_dispatcher.is_readable = c == 'e'
        elif c == 'q':
            remote_dispatcher.dispatch_termination_to_all()
        elif c == 'd':
            process_input_buffer()
        else:
            raise Exception, 'Unknown code: %s' % (c)

    def handle_read(self):
        """Handle all the available character commands in the pipe"""
        while True:
            try:
                c = self.recv(1)
            except OSError, e:
                ok = e.errno == errno.EAGAIN
                assert ok
                return
            else:
                self._do(c)

# All the words that have been typed in gsh. Used by the completion mechanism.
history_words = set()

def complete(text, state):
    """On tab press, return the next possible completion"""
    l = len(text)
    matches = [w for w in history_words if len(w) > l and w.startswith(text)]
    if state <= len(matches):
        return matches[state]

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
            the_stdin_thread.pipe_read, the_stdin_thread.pipe_write = os.pipe()
            the_stdin_thread.wants_control_shell = False
            the_stdin_thread.setDaemon(True)
            the_stdin_thread.start()
            pipe_notification_reader()
        else:
            the_stdin_thread.ready_event.set()

    def run(self):
        while True:
            self.ready_event.wait()
            # The remote processes are ready, the thread can call raw_input
            self.interrupted_event.clear()
            console_output('\r')
            try:
                try:
                    os.write(self.pipe_write, 's')
                    nr = remote_dispatcher.count_completed_processes()[0]
                    readline.set_completer(complete)
                    readline.parse_and_bind('tab: complete')
                    readline.set_completer_delims(' \t\n')
                    cmd = raw_input('ready (%d)> ' % (nr))
                    if self.wants_control_shell:
                        # This seems to be needed if Ctrl-C is hit when some
                        # text is in the line buffer
                        raise EOFError
                    if len(history_words) < 10000:
                        for word in cmd.split():
                            if len(word) > 1:
                                history_words.add(word + ' ')
                finally:
                    os.write(self.pipe_write, 'e')
            except EOFError:
                if self.wants_control_shell:
                    self.ready_event.clear()
                    # Ok, we are no more in raw_input(), tell it to the
                    # main thread
                    self.interrupted_event.set()
                else:
                    os.write(self.pipe_write, 'q')
                    return
            else:
                self.ready_event.clear()
                self.input_buffer.add(cmd + '\n')
                os.write(self.pipe_write, 'd')

the_stdin_thread = stdin_thread()
the_stdin_dispatcher = stdin_dispatcher()
