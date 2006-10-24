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
import sys
import traceback

from gsh.console import set_stdin_blocking

class buffered_dispatcher(asyncore.file_dispatcher):
    """A dispatcher with a write buffer to allow asynchronous writers, and a
    read buffer to permit line oriented manipulations"""

    # 1 MiB should be enough for everybody
    MAX_BUFFER_SIZE = 1 * 1024 * 1024

    class BufferTooLarge(Exception):
        pass

    def __init__(self, fd, name):
        asyncore.file_dispatcher.__init__(self, fd)
        self.fd = fd
        self.name = name
        self.read_buffer = ''
        self.write_buffer = ''

    def handle_error(self):
        """Handle the Ctrl-C or print the exception and its stack trace.
        Returns True if it was an actual error"""
        t, v, tb = sys.exc_info()
        try:
            raise t
        except KeyboardInterrupt:
            # The main loop will launch the control shell
            raise
        except OSError:
            return True
        except:
            set_stdin_blocking(True)
            print t, v
            traceback.print_tb(tb)
            set_stdin_blocking(False)
            return True

    def handle_expt(self):
        # Emulate the select with poll as in: asyncore.loop(use_poll=True)
        self.handle_read()

    def handle_read(self):
        """Some data can be read"""
        if len(self.read_buffer) > buffered_dispatcher.MAX_BUFFER_SIZE:
            raise buffered_dispatcher.BufferTooLarge
        new_data = ''
        while True:
            try:
                piece = self.recv(4096)
            except OSError, e:
                if e.errno == errno.EAGAIN:
                    piece = None
                else:
                    raise
            if not piece:
                self.read_buffer += new_data
                return new_data
            new_data += piece

    def writable(self):
        """Do we have something to write?"""
        return self.write_buffer != ''

    def handle_write(self):
        """Let's write as much as we can"""
        num_sent = self.send(self.write_buffer)
        self.write_buffer = self.write_buffer[num_sent:]

    def dispatch_write(self, buf):
        """Augment the buffer with stuff to write when possible"""
        if len(self.write_buffer) > buffered_dispatcher.MAX_BUFFER_SIZE:
            raise buffered_dispatcher.BufferTooLarge
        self.write_buffer += buf
