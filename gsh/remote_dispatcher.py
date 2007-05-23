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
# Copyright (c) 2006, 2007 Guillaume Chazarain <guichaz@yahoo.fr>

import asyncore
import fcntl
import os
import pty
import random
import signal
import struct
import sys
import termios
import time

from gsh.buffered_dispatcher import buffered_dispatcher
from gsh.console import console_output
from gsh.terminal_size import terminal_size

# Either the remote shell is expecting a command or one is already running
STATE_NOT_STARTED,         \
STATE_IDLE,                \
STATE_EXPECTING_NEXT_LINE, \
STATE_RUNNING,             \
STATE_TERMINATED = range(5)

STATE_NAMES = ['not_started', 'idle', 'expecting_next_line',
               'running', 'terminated']

def all_instances():
    """Iterator over all the remote_dispatcher instances"""
    for i in asyncore.socket_map.itervalues():
        if isinstance(i, remote_dispatcher):
            yield i

def make_unique_name(name):
    display_names = set([i.display_name for i in all_instances()])
    candidate_name = name
    if candidate_name in display_names:
        i = 1
        while True:
            candidate_name = '%s#%d' % (name, i)
            if candidate_name not in display_names:
                break
            i += 1
    return candidate_name

def count_completed_processes():
    """Return a tuple with the number of ready processes and the total number"""
    completed_processes = 0
    total = 0
    for i in all_instances():
        if i.enabled:
            total += 1
            if i.state is STATE_IDLE:
                completed_processes += 1
    return completed_processes, total

def handle_unfinished_lines():
    """Typically we print only lines with a '\n', but if some buffers keep an
    unfinished line for some time we'll add an artificial '\n'"""
    for r in all_instances():
        if r.read_buffer and r.read_buffer[0] != chr(27):
            break
    else:
        # No unfinished lines
        return

    begin = time.time()
    asyncore.loop(count=1, timeout=0.2, use_poll=True)
    duration = time.time() - begin
    if duration >= 0.15:
        for r in all_instances():
            r.print_unfinished_line()

def dispatch_termination_to_all():
    """Start the termination procedure in all remote shells"""
    for r in all_instances():
        r.dispatch_termination()

def all_terminated():
    """For each remote shell we determine if its terminated by checking if
    it is in the right state or if it requested termination but will never
    receive the acknowledgement"""
    for i in all_instances():
        if i.state is not STATE_TERMINATED:
            if i.enabled or not i.termination:
                return False
    return True

def update_terminal_size():
    """Propagate the terminal size to the remote shells accounting for the
    place taken by the longest name"""
    w, h = terminal_size()
    lengths = [len(i.display_name) for i in all_instances() if i.enabled]
    if not lengths:
        return
    max_name_len = max(lengths)
    for i in all_instances():
        padding_len = max_name_len - len(i.display_name)
        new_prefix = i.display_name + padding_len * ' ' + ': '
        if len(new_prefix) < len(i.prefix) and not i.options.interactive:
            # In non-interactive mode, remote processes leave as soon
            # as they are terminated, but we don't want to break the
            # indentation if all the remaining processes have short names.
            return
        i.prefix = new_prefix
    w = max(w - max_name_len - 2, min(w, 10))
    # python bug http://python.org/sf/1112949 on amd64
    # from ajaxterm.py
    bug = struct.unpack('i', struct.pack('I', termios.TIOCSWINSZ))[0]
    packed_size = struct.pack('HHHH', h, w, 0, 0)
    term_size = w, h
    for i in all_instances():
        if i.enabled and i.term_size != term_size:
            i.term_size = term_size
            fcntl.ioctl(i.fd, bug, packed_size)

def format_info(info_list):
    """Turn a 2-dimension list of strings into a 1-dimension list of strings
    with correct spacing"""
    info_list.sort(key=lambda i:int(i[1][3:]))
    max_lengths = []
    if info_list:
        nr_columns = len(info_list[0])
    else:
        nr_columns = 0
    for i in xrange(nr_columns):
        max_lengths.append(max([len(str(info[i])) for info in info_list]))
    for info_id in xrange(len(info_list)):
        info = info_list[info_id]
        for str_id in xrange(len(info)):
            orig_str = str(info[str_id])
            indent = max_lengths[str_id] - len(orig_str)
            info[str_id] = orig_str + indent * ' '
        info_list[info_id] = ' '.join(info)

class remote_dispatcher(buffered_dispatcher):
    """A remote_dispatcher is a ssh process we communicate with"""

    def __init__(self, options, hostname):
        self.pid, fd = pty.fork()
        if self.pid == 0:
            # Child
            self.launch_ssh(options, hostname)
            sys.exit(1)
        # Parent
        self.hostname = hostname
        buffered_dispatcher.__init__(self, fd)
        self.options = options
        self.log_path = None
        self.active = True # deactived shells are dead forever
        self.enabled = True # shells can be enabled and disabled
        self.state = STATE_NOT_STARTED
        self.termination = None
        self.term_size = (-1, -1)
        self.prefix = ''
        self.change_name(hostname)
        self.set_prompt()
        self.pending_rename = None
        if options.command:
            self.dispatch_write(options.command + '\n')
            self.dispatch_termination()

    def launch_ssh(self, options, name):
        """Launch the ssh command in the child process"""
        evaluated = options.ssh % {'host': name}
        shell = os.environ.get('SHELL', '/bin/sh')
        if options.quick_sh:
            evaluated = '%s -t %s sh' % (evaluated, name)
        elif evaluated == options.ssh:
            evaluated = '%s %s' % (evaluated, name)
        os.execlp(shell, shell, '-c', evaluated)

    def set_enabled(self, enabled):
        self.enabled = enabled
        update_terminal_size()

    def change_state(self, state):
        """Change the state of the remote process, logging the change"""
        if state is not self.state:
            if self.is_logging(debug=True):
                self.log('state => %s\n' % (STATE_NAMES[state]), debug=True)
            self.state = state

    def disconnect(self):
        """We are no more interested in this remote process"""
        self.read_buffer = ''
        self.write_buffer = ''
        self.active = False
        self.set_enabled(False)
        if self.options.abort_error and self.state is STATE_NOT_STARTED:
            raise asyncore.ExitNow(1)

    def reconnect(self):
        """Relaunch and reconnect to this same remote process"""
        try:
            os.kill(self.pid, signal.SIGKILL)
        except OSError:
            # The process was already dead, no problem
            pass
        self.close()
        remote_dispatcher(self.options, self.hostname)

    def dispatch_termination(self):
        """Start the termination procedure on this remote process, using the
        same trick as the prompt to hide it"""
        if not self.termination:
            self.term1 = '[gsh termination ' + str(random.random())[2:]
            self.term2 = str(random.random())[2:] + ']'
            self.termination = self.term1 + self.term2
            self.dispatch_write('echo "%s""%s"\n' % (self.term1, self.term2))
            if self.state is not STATE_NOT_STARTED:
                self.change_state(STATE_EXPECTING_NEXT_LINE)

    def set_prompt(self):
        """The prompt is important because we detect the readyness of a process
        by waiting for its prompt. The prompt is built in two parts for it not
        to appear in its building"""
        # No right prompt
        self.dispatch_write('RPS1=\n')
        self.dispatch_write('RPROMPT=\n')
        self.dispatch_write('TERM=ansi\n')
        prompt1 = '[gsh prompt ' + str(random.random())[2:]
        prompt2 = str(random.random())[2:] + ']'
        self.prompt = prompt1 + prompt2
        self.dispatch_write('PS1="%s""%s\n"\n' % (prompt1, prompt2))

    def readable(self):
        """We are always interested in reading from active remote processes if
        the buffer is OK"""
        return self.active and buffered_dispatcher.readable(self)

    def handle_error(self):
        """An exception may or may not lead to a disconnection"""
        if buffered_dispatcher.handle_error(self):
            console_output('Error talking to %s\n ' % (self.display_name),
                           sys.stderr)
            self.disconnect()

    def handle_read_fast_case(self, data):
        """If we are in a fast case we'll avoid the long processing of each
        line"""
        if self.prompt in data or self.state is not STATE_RUNNING or \
           self.termination and (self.term1 in data or self.term2 in data) or \
           self.pending_rename and self.pending_rename in data:
            # Slow case :-(
            return False

        last_nl = data.rfind('\n')
        if last_nl == -1:
            # No '\n' in data => slow case
            return False
        self.read_buffer = data[last_nl + 1:]
        data = data[:last_nl].strip('\n').replace('\r', '\n')
        while True:
            no_empty_lines = data.replace('\n\n', '\n')
            if len(no_empty_lines) == len(data):
                break
            data = no_empty_lines
        if not data:
            return True
        if self.is_logging():
            self.log(data + '\n')
        console_output(self.prefix + \
                       data.replace('\n', '\n' + self.prefix) + '\n')
        return True

    def handle_read(self):
        """We got some output from a remote shell, this is one of the state
        machine"""
        if not self.active:
            return
        new_data = buffered_dispatcher.handle_read(self)
        if self.is_logging(debug=True):
            self.log('==> ' + new_data, debug=True)
        if self.handle_read_fast_case(self.read_buffer):
            return
        lf_pos = new_data.find('\n')
        if lf_pos >= 0:
            # Optimization: we knew there were no '\n' in the previous read
            # buffer, so we searched only in the new_data and we offset the
            # found index by the length of the previous buffer
            lf_pos += len(self.read_buffer) - len(new_data)
        limit = buffered_dispatcher.MAX_BUFFER_SIZE / 10
        if lf_pos < 0 and len(self.read_buffer) > limit:
            # A large unfinished line is treated as a complete line
            # Or maybe there is a '\r' to break the line
            lf_pos = max(new_data.find('\r'), limit)
            
        while lf_pos >= 0:
            # For each line in the buffer
            line = self.read_buffer[:lf_pos + 1]
            if self.prompt in line:
                if self.options.interactive:
                    self.change_state(STATE_IDLE)
                else:
                    self.change_state(STATE_EXPECTING_NEXT_LINE)
            elif self.termination and self.termination in line:
                self.change_state(STATE_TERMINATED)
                self.disconnect()
            elif self.termination and self.term1 in line and self.term2 in line:
                # Just ignore this line
                pass
            elif self.pending_rename and self.pending_rename in line:
                self.received_rename(line)
            elif self.state is STATE_EXPECTING_NEXT_LINE:
                self.change_state(STATE_RUNNING)
            elif self.state is STATE_RUNNING:
                line = line.replace('\r', '\n')
                if line[-1] != '\n':
                    line += '\n'
                if self.is_logging():
                    self.log(line)
                if line.strip():
                    console_output(self.prefix + line)

            # Go to the next line in the buffer
            self.read_buffer = self.read_buffer[lf_pos + 1:]
            if self.handle_read_fast_case(self.read_buffer):
                return
            lf_pos = self.read_buffer.find('\n')

    def print_unfinished_line(self):
        """The unfinished line stayed long enough in the buffer to be printed"""
        if self.state is STATE_RUNNING:
            line = self.read_buffer + '\n'
            self.read_buffer = ''
            if self.is_logging():
                self.log(line)
            console_output(self.prefix + line)

    def writable(self):
        """Do we want to write something?"""
        return self.active and buffered_dispatcher.writable(self)

    def is_logging(self, debug=False):
        if debug:
            return self.options.debug
        return self.log_path is not None

    def log(self, msg, debug=False):
        """Log some information, either to a file or on the console"""
        if self.log_path is None:
            if debug and self.options.debug:
                state = STATE_NAMES[self.state]
                msg = msg.encode('string_escape')
                console_output('[dbg] %s[%s]: %s\n' %
                                (self.display_name, state, msg))
        else:
            # None != False, that's why we use 'not'
            if (not debug) == (not self.options.debug):
                log = os.open(self.log_path,
                              os.O_WRONLY|os.O_APPEND|os.O_CREAT, 0664)
                os.write(log, msg)
                os.close(log)

    def get_info(self):
        """Return a list will all information available about this process"""
        if self.active:
            state = STATE_NAMES[self.state]
        else:
            state = ''

        return [self.display_name, 'fd:%d' % (self.fd),
                'r:%d' % (len(self.read_buffer)),
                'w:%d' % (len(self.write_buffer)),
                self.active and 'active' or 'dead',
                self.enabled and 'enabled' or 'disabled',
                state]

    def dispatch_write(self, buf):
        """There is new stuff to write when possible"""
        if self.active and self.enabled:
            if self.is_logging(debug=True):
                self.log('<== ' + buf, debug=True)
            buffered_dispatcher.dispatch_write(self, buf)

    def change_name(self, name):
        self.display_name = None
        self.display_name = make_unique_name(name)
        update_terminal_size()
        if self.options.log_dir:
            # The log file
            filename = self.display_name.replace('/', '_')
            log_path = os.path.join(self.options.log_dir, filename)
            if self.log_path:
                # Rename the previous log
                os.rename(self.log_path, log_path)
            self.log_path = log_path

    def rename(self, string):
        previous_name = self.display_name
        if string:
            pending_rename1 = str(random.random())[2:] + ','
            pending_rename2 = str(random.random())[2:] + ':'
            self.pending_rename = pending_rename1 + pending_rename2
            self.dispatch_write('echo "%s""%s" %s\n' %
                                    (pending_rename1, pending_rename2, string))
            self.change_state(STATE_EXPECTING_NEXT_LINE)
        else:
            self.change_name(self.hostname)

    def received_rename(self, line):
        new_name = line[len(self.pending_rename) + 1:-1]
        self.change_name(new_name)
        self.pending_rename = None

    def __str__(self):
        return self.display_name
