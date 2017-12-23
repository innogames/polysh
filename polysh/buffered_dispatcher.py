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
# Copyright (c) 2006 Guillaume Chazarain <guichaz@gmail.com>

import asyncore
import errno
import fcntl
import os

from polysh.console import console_output

class buffered_dispatcher(asyncore.file_dispatcher):
    """A dispatcher with a write buffer to allow asynchronous writers, and a
    read buffer to permit line oriented manipulations"""

    # 1 MiB should be enough for everybody
    MAX_BUFFER_SIZE = 1 * 1024 * 1024

    def __init__(self, fd):
        asyncore.file_dispatcher.__init__(self, fd)
        self.fd = fd
        self.read_buffer = b''
        self.write_buffer = b''
        self.allow_write = True

    def handle_read(self):
        """Some data can be read"""
        new_data = b''
        buffer_length = len(self.read_buffer)
        try:
            while buffer_length < buffered_dispatcher.MAX_BUFFER_SIZE:
                try:
                    piece = self.recv(4096)
                except OSError as e:
                    if e.errno == errno.EAGAIN:
                        # End of the available data
                        break
                    elif e.errno == errno.EIO and new_data:
                        # Hopefully we could read an error message before the
                        # actual termination
                        break
                    else:
                        raise
                new_data += piece
                buffer_length += len(piece)
        finally:
            new_data = new_data.replace(b'\r', b'\n')
            self.read_buffer += new_data
        return new_data

    def readable(self):
        """No need to ask data if our buffer is already full"""
        return len(self.read_buffer) < buffered_dispatcher.MAX_BUFFER_SIZE

    def writable(self):
        """Do we have something to write?"""
        return self.write_buffer != b''

    def dispatch_write(self, buf):
        """Augment the buffer with stuff to write when possible"""
        assert isinstance(buf, bytes)
        assert self.allow_write
        self.write_buffer += buf
        if len(self.write_buffer) > buffered_dispatcher.MAX_BUFFER_SIZE:
            console_output('Buffer too big (%d) for %s\n' %
                                            (len(self.write_buffer), str(self)))
            raise asyncore.ExitNow(1)

    def drain_and_block_writing(self):
        # set the fd to blocking mode
        self.allow_write = False
        flags = fcntl.fcntl(self.fd, fcntl.F_GETFL, 0)
        flags = flags & ~os.O_NONBLOCK
        fcntl.fcntl(self.fd, fcntl.F_SETFL, flags)
        if self.writable():
            self.handle_write()

    def allow_writing(self):
        # set the fd to non-blocking mode
        flags = fcntl.fcntl(self.fd, fcntl.F_GETFL, 0)
        flags = flags | os.O_NONBLOCK
        fcntl.fcntl(self.fd, fcntl.F_SETFL, flags)
        self.allow_write = True
