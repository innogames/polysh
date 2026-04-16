"""Polysh - Buffered Dispatcher Class

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

import errno
import fcntl
import os
import sys

from polysh import dispatcher_registry
from polysh.console import console_output
from polysh.exceptions import ExitNow

_TRACE = os.environ.get('POLYSH_TRACE')


def _trace(msg: str) -> None:
    if _TRACE:
        print(f'[trace] {msg}', file=sys.stderr, flush=True)


class BufferedDispatcher:
    """A dispatcher with a write buffer to allow asynchronous writers, and a
    read buffer to permit line oriented manipulations"""

    # 1 MiB should be enough for everybody
    MAX_BUFFER_SIZE = 1 * 1024 * 1024

    def __init__(self, fd: int) -> None:
        self.fd = fd
        self.read_buffer = b''
        self.write_buffer = b''

        # Set non-blocking mode
        flags = fcntl.fcntl(fd, fcntl.F_GETFL)
        fcntl.fcntl(fd, fcntl.F_SETFL, flags | os.O_NONBLOCK)

        # Register with the dispatcher registry
        dispatcher_registry.register(fd, self)

    def recv(self, buffer_size: int) -> bytes:
        """Read from the file descriptor."""
        return os.read(self.fd, buffer_size)

    def send(self, data: bytes) -> int:
        """Write to the file descriptor."""
        return os.write(self.fd, data)

    def close(self) -> None:
        """Unregister and close the file descriptor."""
        dispatcher_registry.unregister(self.fd)
        try:
            os.close(self.fd)
        except OSError:
            pass

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
                        _trace(f'  _handle_read_chunk fd={self.fd}: EAGAIN after {len(new_data)}B')
                        break
                    if e.errno == errno.EIO and new_data:
                        # Hopefully we could read an error message before the
                        # actual termination
                        _trace(f'  _handle_read_chunk fd={self.fd}: EIO with {len(new_data)}B partial data')
                        break
                    _trace(f'  _handle_read_chunk fd={self.fd}: OSError errno={e.errno} raising')
                    raise

                if not piece:
                    # A closed connection is indicated by signaling a read
                    # condition, and having recv() return 0.
                    # On macOS, pty master reads return 0 (EOF) after child
                    # exit, whereas Linux raises EIO.  If we already have
                    # partial data, return it first; the next call will see
                    # EOF again and raise to trigger handle_close().
                    if not new_data:
                        _trace(f'  _handle_read_chunk fd={self.fd}: EOF (0 bytes), raising synthetic EIO')
                        raise OSError(errno.EIO, 'Connection closed (EOF)')
                    _trace(f'  _handle_read_chunk fd={self.fd}: EOF after {len(new_data)}B partial, deferring close')
                    break

                new_data += piece
                buffer_length += len(piece)

        finally:
            new_data = new_data.replace(b'\r', b'\n')
            self.read_buffer += new_data
        _trace(f'  _handle_read_chunk fd={self.fd}: returning {len(new_data)}B, buf now {len(self.read_buffer)}B')
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
            console_output(
                f'Buffer too big ({len(self.write_buffer):d}) for {str(self)}\n'.encode()
            )
            raise ExitNow(1)
        return True
