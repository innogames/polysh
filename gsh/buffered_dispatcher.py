import asyncore
import sys
import traceback

from gsh import control_shell
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
            control_shell.singleton.launch()
            return False
        except OSError:
            return True
        except:
            set_stdin_blocking(True)
            print t, v
            traceback.print_tb(tb)
            set_stdin_blocking(False)
            return True

    def handle_read(self):
        """Some data can be read"""
        new_data = self.recv(4096)
        self.read_buffer += new_data
        if len(self.read_buffer) > buffered_dispatcher.MAX_BUFFER_SIZE:
            raise buffered_dispatcher.BufferTooLarge
        return new_data

    def writable(self):
        """Do we have something to write?"""
        return self.write_buffer != ''

    def handle_write(self):
        """Let's write as much as we can"""
        num_sent = self.send(self.write_buffer)
        self.write_buffer = self.write_buffer[num_sent:]

    def dispatch_write(self, buf):
        """Augment the buffer with stuff to write when possible"""
        self.write_buffer += buf
        if len(self.write_buffer) > buffered_dispatcher.MAX_BUFFER_SIZE:
            raise buffered_dispatcher.BufferTooLarge
