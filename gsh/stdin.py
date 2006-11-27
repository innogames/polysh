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
import errno
import os
import readline # Just to say we want to use it with raw_input
from threading import Thread, Event, Lock

from gsh import remote_dispatcher

class command_buffer(object):
    def __init__(self):
        self.lock = Lock()
        self.commands = []

    def add_cmd(self, cmd):
        self.lock.acquire()
        try:
            self.commands.append(cmd)
        finally:
            self.lock.release()

    def get_cmd(self):
        self.lock.acquire()
        try:
            if self.commands:
                return self.commands.pop()
        finally:
            self.lock.release()

class pipe_notification_reader(asyncore.file_dispatcher):
    def __init__(self):
        asyncore.file_dispatcher.__init__(self, the_stdin_thread.pipe_read)

    def handle_read(self):
        # Drain the pipe, which must not be very large
        if 'q' in self.recv(4096):
            raise asyncore.ExitNow
        try:
            self.recv(4096)
        except OSError, e:
            ok = e.errno == errno.EAGAIN
        assert ok

        while True:
            cmd = the_stdin_thread.commands.get_cmd()
            if not cmd:
                break
            cmd += '\n'
            for r in remote_dispatcher.all_instances():
                r.dispatch_write(cmd)
                r.log('<== ' + cmd)
                if r.enabled and r.state != remote_dispatcher.STATE_NOT_STARTED:
                    r.change_state(remote_dispatcher.STATE_EXPECTING_NEXT_LINE)

class stdin_thread(Thread):
    def __init__(self):
        Thread.__init__(self, name='stdin thread')

    @staticmethod
    def activate(interactive):
        the_stdin_thread.ready_event = Event()
        if interactive:
            the_stdin_thread.interrupted_event = Event()
            the_stdin_thread.commands = command_buffer()
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
            print
            try:
                cmd = raw_input('> ')
            except EOFError:
                if self.wants_control_shell:
                    self.ready_event.clear()
                    self.interrupted_event.set()
                else:
                    os.write(self.pipe_write, 'q')
                    return
            else:
                self.ready_event.clear()
                self.commands.add_cmd(cmd)
                os.write(self.pipe_write, '1')

the_stdin_thread = stdin_thread()
