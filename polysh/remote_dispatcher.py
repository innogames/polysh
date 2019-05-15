"""Polysh - Remote Shell Dispatcher

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
import os
import pty
import signal
import sys
import termios
import select
import platform

from polysh.buffered_dispatcher import BufferedDispatcher
from polysh import callbacks
from polysh.console import console_output
from polysh import display_names

options = None  # type: Optional[Namespace]

# Either the remote shell is expecting a command or one is already running
STATE_NAMES = ['not_started', 'idle', 'running', 'terminated', 'dead']

STATE_NOT_STARTED,         \
    STATE_IDLE,                \
    STATE_RUNNING,             \
    STATE_TERMINATED,          \
    STATE_DEAD = list(range(len(STATE_NAMES)))

# Terminal color codes
COLORS = [1] + list(range(30, 37))

# Count the total number of RemoteDispatcher.handle_read() invocations
nr_handle_read = 0


def main_loop_iteration(timeout=None):
    """Return the number of RemoteDispatcher.handle_read() calls made by this
    iteration"""
    prev_nr_read = nr_handle_read
    asyncore.loop(count=1, timeout=timeout, use_poll=True)
    return nr_handle_read - prev_nr_read


def log(msg):
    assert isinstance(msg, bytes)
    if options.log_file:
        fd = options.log_file.fileno()
        while msg:
            try:
                written = os.write(fd, msg)
            except OSError as e:
                print('Exception while writing log:', options.log_file.name)
                print(e)
                raise asyncore.ExitNow(1)
            msg = msg[written:]


class RemoteDispatcher(BufferedDispatcher):
    """A RemoteDispatcher is a ssh process we communicate with"""

    def __init__(self, hostname, port):
        assert isinstance(hostname, str)
        assert isinstance(port, str)

        if port != "22":
            port = "-p " + port
        else:
            port = ''

        self.pid, fd = pty.fork()
        if self.pid == 0:
            # Child
            self.launch_ssh(hostname, port)
            sys.exit(1)

        # Parent
        super().__init__(fd)
        self.temporary = False
        self.hostname = hostname
        self.port = port
        self.debug = options.debug
        self.enabled = True  # shells can be enabled and disabled
        self.state = STATE_NOT_STARTED
        self.term_size = (-1, -1)
        self.display_name = None
        self.change_name(self.hostname.encode())
        self.init_string = self.configure_tty() + self.set_prompt()
        self.init_string_sent = False
        self.read_in_state_not_started = b''
        self.command = options.command
        self.last_printed_line = b''
        if sys.stdout.isatty() and not options.disable_color:
            COLORS.insert(0, COLORS.pop())  # Rotate the colors
            self.color_code = COLORS[0]
        else:
            self.color_code = None

    def launch_ssh(self, name, port):
        """Launch the ssh command in the child process"""
        if options.user:
            name = '%s@%s' % (options.user, name)
        evaluated = options.ssh % {'host': name, 'port': port}
        if evaluated == options.ssh:
            evaluated = '%s %s' % (evaluated, name)
        os.execlp('/bin/sh', 'sh', '-c', evaluated)

    def set_enabled(self, enabled):
        if enabled != self.enabled and options.interactive:
            # In non-interactive mode, remote processes leave as soon
            # as they are terminated, but we don't want to break the
            # indentation if all the remaining processes have short names.
            display_names.set_enabled(self.display_name, enabled)
        self.enabled = enabled

    def change_state(self, state):
        """Change the state of the remote process, logging the change"""
        if state is not self.state:
            if self.debug:
                self.print_debug(b'state => ' + STATE_NAMES[state].encode())
            if self.state is STATE_NOT_STARTED:
                self.read_in_state_not_started = b''
            self.state = state

    def disconnect(self):
        """We are no more interested in this remote process"""
        try:
            os.kill(-self.pid, signal.SIGKILL)
        except OSError:
            # The process was already dead, no problem
            pass
        self.read_buffer = b''
        self.write_buffer = b''
        self.set_enabled(False)
        if self.read_in_state_not_started:
            self.print_lines(self.read_in_state_not_started)
            self.read_in_state_not_started = b''
        if options.abort_error and self.state is STATE_NOT_STARTED:
            raise asyncore.ExitNow(1)
        self.change_state(STATE_DEAD)

    def configure_tty(self):
        """We don't want \n to be replaced with \r\n, and we disable the echo"""
        attr = termios.tcgetattr(self.fd)
        attr[1] &= ~termios.ONLCR  # oflag
        attr[3] &= ~termios.ECHO  # lflag
        termios.tcsetattr(self.fd, termios.TCSANOW, attr)
        # unsetopt zle prevents Zsh from resetting the tty
        return b'unsetopt zle 2> /dev/null;stty -echo -onlcr -ctlecho;'

    def seen_prompt_cb(self, unused):
        if options.interactive:
            self.change_state(STATE_IDLE)
        elif self.command:
            p1, p2 = callbacks.add(b'real prompt ends', lambda d: None, True)
            self.dispatch_command(b'PS1="' + p1 + b'""' + p2 + b'\n"\n')
            self.dispatch_command(self.command.encode() + b'\n')
            self.dispatch_command(b'exit 2>/dev/null\n')
            self.command = None

    def set_prompt(self):
        """The prompt is important because we detect the readyness of a process
        by waiting for its prompt."""
        # No right prompt
        command_line = b'PS2=;RPS1=;RPROMPT=;'
        command_line += b'PROMPT_COMMAND=;'
        command_line += b'TERM=ansi;'
        command_line += b'unset precmd_functions;'
        command_line += b'unset HISTFILE;'
        prompt1, prompt2 = callbacks.add(b'prompt', self.seen_prompt_cb, True)
        command_line += b'PS1="' + prompt1 + b'""' + prompt2 + b'\n"\n'
        return command_line

    def readable(self):
        """We are always interested in reading from active remote processes if
        the buffer is OK"""
        return (self.state != STATE_DEAD and
                super().readable())

    def handle_expt(self):
        # Dirty hack to ignore POLLPRI flag that is raised on Mac OS, but not
        # on linux. asyncore calls this method in case POLLPRI flag is set, but
        # self.socket.getsockopt(socket.SOL_SOCKET, socket.SO_ERROR) == 0
        if platform.system() == 'Darwin' and select.POLLPRI:
            return

        self.handle_close()

    def handle_close(self):
        if self.state is STATE_DEAD:
            # This connection has already been killed. Asyncore has probably
            # called handle_close() or handle_expt() on this connection twice.
            return

        pid, status = os.waitpid(self.pid, 0)
        exit_code = os.WEXITSTATUS(status)
        options.exit_code = max(options.exit_code, exit_code)
        if exit_code and options.interactive:
            console_output('Error talking to {}\n'.format(
                self.display_name).encode())
        self.disconnect()
        if self.temporary:
            self.close()

    def print_lines(self, lines):
        assert isinstance(lines, bytes)
        from polysh.display_names import max_display_name_length
        lines = lines.strip(b'\n')
        while True:
            no_empty_lines = lines.replace(b'\n\n', b'\n')
            if len(no_empty_lines) == len(lines):
                break
            lines = no_empty_lines
        if not lines:
            return
        indent = max_display_name_length - len(self.display_name)
        log_prefix = self.display_name.encode() + indent * b' ' + b' : '
        if self.color_code is None:
            console_prefix = log_prefix
        else:
            console_prefix = (b'\033[1;' + str(self.color_code).encode() +
                              b'm' + log_prefix + b'\033[1;m')
        console_data = (console_prefix +
                        lines.replace(b'\n', b'\n' + console_prefix) + b'\n')
        log_data = (log_prefix +
                    lines.replace(b'\n', b'\n' + log_prefix) + b'\n')
        console_output(console_data, logging_msg=log_data)
        self.last_printed_line = lines[lines.rfind(b'\n') + 1:]

    def handle_read_fast_case(self, data):
        """If we are in a fast case we'll avoid the long processing of each
        line"""
        if self.state is not STATE_RUNNING or callbacks.any_in(data):
            # Slow case :-(
            return False

        last_nl = data.rfind(b'\n')
        if last_nl == -1:
            # No '\n' in data => slow case
            return False
        self.read_buffer = data[last_nl + 1:]
        self.print_lines(data[:last_nl])
        return True

    def handle_read(self):
        """We got some output from a remote shell, this is one of the state
        machine"""
        if self.state == STATE_DEAD:
            return
        global nr_handle_read
        nr_handle_read += 1
        new_data = self._handle_read_chunk()
        if self.debug:
            self.print_debug(b'==> ' + new_data)
        if self.handle_read_fast_case(self.read_buffer):
            return
        lf_pos = new_data.find(b'\n')
        if lf_pos >= 0:
            # Optimization: we knew there were no '\n' in the previous read
            # buffer, so we searched only in the new_data and we offset the
            # found index by the length of the previous buffer
            lf_pos += len(self.read_buffer) - len(new_data)
        elif self.state is STATE_NOT_STARTED and \
                options.password is not None and \
                b'password:' in self.read_buffer.lower():
            self.dispatch_write('{}\n'.format(options.password).encode())
            self.read_buffer = b''
            return
        while lf_pos >= 0:
            # For each line in the buffer
            line = self.read_buffer[:lf_pos + 1]
            if callbacks.process(line):
                pass
            elif self.state in (STATE_IDLE, STATE_RUNNING):
                self.print_lines(line)
            elif self.state is STATE_NOT_STARTED:
                self.read_in_state_not_started += line
                if b'The authenticity of host' in line:
                    msg = line.strip(b'\n') + b' Closing connection.'
                    self.disconnect()
                elif b'REMOTE HOST IDENTIFICATION HAS CHANGED' in line:
                    msg = b'Remote host identification has changed.'
                else:
                    msg = None

                if msg:
                    self.print_lines(msg + b' Consider manually connecting or '
                                     b'using ssh-keyscan.')

            # Go to the next line in the buffer
            self.read_buffer = self.read_buffer[lf_pos + 1:]
            if self.handle_read_fast_case(self.read_buffer):
                return
            lf_pos = self.read_buffer.find(b'\n')
        if self.state is STATE_NOT_STARTED and not self.init_string_sent:
            self.dispatch_write(self.init_string)
            self.init_string_sent = True

    def print_unfinished_line(self):
        """The unfinished line stayed long enough in the buffer to be printed"""
        if self.state is STATE_RUNNING:
            if not callbacks.process(self.read_buffer):
                self.print_lines(self.read_buffer)
            self.read_buffer = b''

    def writable(self):
        """Do we want to write something?"""
        return (self.state != STATE_DEAD and
                super().writable())

    def handle_write(self):
        """Let's write as much as we can"""
        num_sent = self.send(self.write_buffer)
        if self.debug:
            if self.state is not STATE_NOT_STARTED or options.password is None:
                self.print_debug(b'<== ' + self.write_buffer[:num_sent])
        self.write_buffer = self.write_buffer[num_sent:]

    def print_debug(self, msg):
        """Log some debugging information to the console"""
        assert isinstance(msg, bytes)
        state = STATE_NAMES[self.state].encode()
        console_output(b'[dbg] ' + self.display_name.encode() + b'[' + state +
                       b']: ' + msg + b'\n')

    def get_info(self):
        """Return a list with all information available about this process"""
        return [self.display_name.encode(),
                self.enabled and b'enabled' or b'disabled',
                STATE_NAMES[self.state].encode() + b':',
                self.last_printed_line.strip()]

    def dispatch_write(self, buf):
        """There is new stuff to write when possible"""
        if self.state != STATE_DEAD and self.enabled:
            super().dispatch_write(buf)
            return True
        return False

    def dispatch_command(self, command):
        if self.dispatch_write(command):
            self.change_state(STATE_RUNNING)

    def change_name(self, new_name):
        """Change the name of the shell, possibly updating the maximum name
        length"""
        if not new_name:
            name = self.hostname
        else:
            name = new_name.decode()
        self.display_name = display_names.change(
            self.display_name, name)

    def rename(self, name):
        """Send to the remote shell, its new name to be shell expanded"""
        if name:
            # defug callback add?
            rename1, rename2 = callbacks.add(
                b'rename', self.change_name, False)
            self.dispatch_command(b'/bin/echo "' + rename1 + b'""' + rename2 +
                                  b'"' + name + b'\n')
        else:
            self.change_name(self.hostname.encode())

    def close(self):
        display_names.change(self.display_name, None)
        super().close()
