import asyncore
import atexit
import sys

from gsh.buffered_dispatcher import buffered_dispatcher
from gsh.console import set_stdin_blocking, console_output
from gsh import remote_dispatcher

class stdin_reader(buffered_dispatcher):
    """All streams are handled in the select loop, including stdin"""

    def __init__(self, options):
        set_stdin_blocking(False)
        atexit.register(set_stdin_blocking, True)
        buffered_dispatcher.__init__(self, sys.stdin.fileno(), '__stdin__')
        self.opened = True

    def handle_close(self):
        """Handle Ctrl-D"""
        for r in remote_dispatcher.all_instances():
            r.dispatch_termination()
        self.opened = False

    def readable(self):
        return self.opened

    def handle_read(self):
        """The user entered some commands, send them"""
        try:
            new_data = buffered_dispatcher.handle_read(self)
        except buffered_dispatcher.BufferTooLarge:
            console_output('stdin read buffer too large\n', sys.stderr)
            raise asyncore.ExitNow

        lf_pos = self.read_buffer.find('\n')
        while lf_pos >= 0:
            line = self.read_buffer[:lf_pos + 1]
            for r in remote_dispatcher.all_instances():
                r.dispatch_write(line)
                r.log('<== ' + line)
                if r.enabled and r.state != remote_dispatcher.STATE_NOT_STARTED:
                    r.change_state(remote_dispatcher.STATE_EXPECTING_NEXT_LINE)
            self.read_buffer = self.read_buffer[lf_pos + 1:]
            lf_pos = self.read_buffer.find('\n')
