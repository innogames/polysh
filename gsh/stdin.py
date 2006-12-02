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
from threading import Thread, Event, Lock

from gsh import remote_dispatcher
from gsh.console import set_blocking_stdin, console_output

def restore_streams_flags_at_exit():
    get_flags = lambda fd: (fd, fcntl.fcntl(fd, fcntl.F_GETFL, 0))
    flags = map(get_flags, range(3))
    set_flags = lambda (fd, flags): fcntl.fcntl(fd, fcntl.F_SETFL, flags)
    atexit.register(map, set_flags, flags)

class stdin_dispatcher(asyncore.file_dispatcher):
    def __init__(self):
        asyncore.file_dispatcher.__init__(self, 0)
        self.is_readable = True

    def readable(self):
        return self.is_readable

    def writable(self):
        return False

    def handle_close(self):
        remote_dispatcher.dispatch_termination_to_all()

    def handle_read(self):
        while True:
            try:
                data = self.recv(4096)
            except OSError, e:
                if e.errno == errno.EAGAIN:
                    break
                else:
                    raise
            else:
                if data:
                    the_stdin_thread.input_buffer.add(data)
                    process_input_buffer()
                else:
                    self.is_readable = False
                    break

class input_buffer(object):
    def __init__(self):
        self.lock = Lock()
        self.buf = ''

    def add(self, data):
        self.lock.acquire()
        try:
            self.buf += data
        finally:
            self.lock.release()
            

    def get(self):
        self.lock.acquire()
        try:
            data = self.buf
            if data:
                self.buf = ''
                return data
        finally:
            self.lock.release()

def process_input_buffer():
    data = the_stdin_thread.input_buffer.get()
    if not data:
        return
    for r in remote_dispatcher.all_instances():
        r.dispatch_write(data)
        r.log('<== ' + data)
        if r.enabled and r.state == remote_dispatcher.STATE_IDLE:
            r.change_state(remote_dispatcher.STATE_EXPECTING_NEXT_LINE)

# Pipe character protocol:
# s: entering in raw_input, the main loop should not read stdin
# e: leaving raw_input, the main loop can read stdin
# q: Ctrl-D was pressed, exiting
# d: there is new data to send

class pipe_notification_reader(asyncore.file_dispatcher):
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
        while True:
            try:
                c = self.recv(1)
            except OSError, e:
                ok = e.errno == errno.EAGAIN
                assert ok
                return
            else:
                self._do(c)

class stdin_thread(Thread):
    def __init__(self):
        Thread.__init__(self, name='stdin thread')

    @staticmethod
    def activate(interactive):
        the_stdin_thread.ready_event = Event()
        if interactive:
            the_stdin_thread.interrupted_event = Event()
            the_stdin_thread.input_buffer = input_buffer()
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
            self.interrupted_event.clear()
            console_output('\r')
            set_blocking_stdin(True)
            try:
                try:
                    os.write(self.pipe_write, 's')
                    nr = remote_dispatcher.count_completed_processes()[0]
                    cmd = raw_input('gsh (%d)> ' % (nr))
                finally:
                    set_blocking_stdin(False)
                    os.write(self.pipe_write, 'e')
            except EOFError:
                if self.wants_control_shell:
                    self.ready_event.clear()
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
