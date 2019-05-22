"""Polysh - Buffered Dispatcher Class

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

from polysh.console import console_output


class BufferedDispatcher(asyncore.file_dispatcher):
    """A dispatcher with a write buffer to allow asynchronous writers, and a
    read buffer to permit line oriented manipulations"""

    # 1 MiB should be enough for everybody
    MAX_BUFFER_SIZE = 1 * 1024 * 1024

    def __init__(self, fd: int) -> None:
        asyncore.file_dispatcher.__init__(self, fd)
        self.fd = fd
        self.read_buffer = b''
        self.write_buffer = b''

    def handle_read(self) -> None:
        self._handle_read_chunk()

    def _handle_read_chunk(self) -> bytes:
        """Some data can be read"""
        new_data = b''
        buffer_length = len(self.read_buffer)
        try:
            while buffer_length < self.MAX_BUFFER_SIZE:
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

                if not piece:
                    # A closed connection is indicated by signaling a read
                    # condition, and having recv() return 0.
                    break

                new_data += piece
                buffer_length += len(piece)

        finally:
            new_data = new_data.replace(b'\r', b'\n')
            self.read_buffer += new_data
        return new_data

    def readable(self) -> bool:
        """No need to ask data if our buffer is already full"""
        return len(self.read_buffer) < self.MAX_BUFFER_SIZE

    def writable(self) -> bool:
        """Do we have something to write?"""
        return self.write_buffer != b''

    def dispatch_write(self, buf: bytes) -> bool:
        """Augment the buffer with stuff to write when possible"""
        self.write_buffer += buf
        if len(self.write_buffer) > self.MAX_BUFFER_SIZE:
            console_output('Buffer too big ({:d}) for {}\n'.format(
                len(self.write_buffer), str(self)).encode())
            raise asyncore.ExitNow(1)
        return True
