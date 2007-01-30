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
import os
import pty
import random
import signal
import sys
import time

from gsh.buffered_dispatcher import buffered_dispatcher
from gsh.console import console_output

# Either the remote shell is expecting a command, or we are waiting
# for the first line (options.print_first), or we already printed the
# first line and a command is running
STATE_NOT_STARTED,         \
STATE_IDLE,                \
STATE_EXPECTING_NEXT_LINE, \
STATE_EXPECTING_LINE,      \
STATE_RUNNING,             \
STATE_TERMINATED = range(6)

STATE_NAMES = ['not_started', 'idle', 'expecting_next_line',
                'expecting_line', 'running', 'terminated']

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
        if r.read_buffer:
            break
    else:
        # No unfinished lines
        return

    begin = time.time()
    asyncore.loop(count=1,timeout=0.2)
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
        self.change_name(hostname)
        self.active = True # deactived shells are dead forever
        self.enabled = True # shells can be enabled and disabled
        self.options = options
        if options.log_dir:
            # Open the log file
            log_path = os.path.join(options.log_dir, hostname.replace('/', '_'))
            self.log_file = os.open(log_path, os.O_WRONLY|os.O_CREAT, 0644)
            os.ftruncate(self.log_file, 0)
        else:
            self.log_file = None

        self.state = STATE_NOT_STARTED
        self.termination = None
        self.set_prompt()
        self.pending_rename = None
        if options.command:
            self.dispatch_write(options.command + '\n')
            self.dispatch_termination()
            self.options.interactive = False
        else:
            self.options.interactive = sys.stdin.isatty()

    def launch_ssh(self, options, name):
        """Launch the ssh command in the child process"""
        if options.ssh_shell_cmd:
            shell = os.environ.get('SHELL', '/bin/sh')
            evaluated = options.ssh_shell_cmd % {'host': name}
            if evaluated == options.ssh_shell_cmd:
                evaluated = '%s %s' % (options.ssh_shell_cmd, name)
            exec_args = (shell, '-c', evaluated)
        else:
            exe = options.ssh_exec or 'ssh'
            evaluated = exe % {'host': name}
            if evaluated == exe:
                exec_args = (exe, name)
            else:
                exec_args = (evaluated)
        os.execlp(exec_args[0], *exec_args)

    def change_state(self, state):
        """Change the state of the remote process, logging the change"""
        self.log(('state => ', STATE_NAMES[state], '\n'), debug=True)
        self.state = state

    def disconnect(self):
        """We are no more interested in this remote process"""
        self.read_buffer = ''
        self.write_buffer = ''
        self.active = False
        self.enabled = False
        if self.options.abort_error:
            raise asyncore.ExitNow

    def reconnect(self):
        """Relaunch and reconnect to this same remote process"""
        os.kill(self.pid, signal.SIGKILL)
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
        """We are always interested in reading from active remote processes"""
        return self.active

    def handle_error(self):
        """An exception may or may not lead to a disconnection"""
        if buffered_dispatcher.handle_error(self):
            console_output('Error talking to %s\n ' % (self.display_name),
                           sys.stderr)
            self.disconnect()

    def handle_read(self):
        """We got some output from a remote shell, this is one of the state
        machine"""
        if not self.active:
            return
        new_data = buffered_dispatcher.handle_read(self)
        self.log(('==> ', new_data), debug=True)
        lf_pos = new_data.find('\n')
        if lf_pos >= 0:
            # Optimization: we knew there were no '\n' in the previous read
            # buffer, so we searched only in the new_data and we offset the
            # found index by the length of the previous buffer
            lf_pos += len(self.read_buffer) - len(new_data)
        limit = buffered_dispatcher.MAX_BUFFER_SIZE / 10
        if lf_pos < 0 and len(self.read_buffer) > limit:
            # A large unfinished line is treated as a complete line
            lf_pos = limit
        while lf_pos >= 0:
            # For each line in the buffer
            line = self.read_buffer[:lf_pos - 1]
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
                self.change_state(STATE_EXPECTING_LINE)
            elif self.state is not STATE_NOT_STARTED:
                self.log((line, '\n'))
                if not self.options.print_first or \
                   self.state is STATE_EXPECTING_LINE:
                    console_output(self.display_name + ': ' + line + '\n')
                    self.change_state(STATE_RUNNING)

            # Go to the next line in the buffer
            self.read_buffer = self.read_buffer[lf_pos + 1:]
            lf_pos = self.read_buffer.find('\n')

    def print_unfinished_line(self):
        """The unfinished line stayed long enough in the buffer to be printed"""
        if self.state in (STATE_EXPECTING_LINE, STATE_RUNNING):
            if not self.options.print_first or \
               self.state is STATE_EXPECTING_LINE:
                    line = self.read_buffer + '\n'
                    self.read_buffer = ''
                    self.log((line,))
                    console_output(self.display_name + ': ' + line)

    def writable(self):
        """Do we want to write something?"""
        return self.active and buffered_dispatcher.writable(self)

    def log(self, msgs, debug=False):
        """Log some information, either to a file or on the console"""
        if self.log_file is None:
            if debug and self.options.debug:
                state = STATE_NAMES[self.state]
                console_output('[dbg] %s[%s]: %s' %
                                (self.display_name, state, ''.join(msgs)))
        else:
            # None != False, that's why we use 'not'
            if (not debug) == (not self.options.debug):
                os.write(self.log_file, ''.join(msgs))

    def get_info(self):
        """Return a list will all information available about this process"""
        if self.active:
            state = STATE_NAMES[self.state]
        else:
            state = ''

        return [self.display_name, 'fd:%d' % (self.fd),
                'r:%d' % (len(self.read_buffer)),
                'w:%d' % (len(self.write_buffer)),
                'active:%s' % (str(self.active)),
                'enabled:%s' % (str(self.enabled)), state]

    def dispatch_write(self, buf):
        """There is new stuff to write when possible"""
        if self.active and self.enabled:
            self.log(('<== ', buf), debug=True)
            buffered_dispatcher.dispatch_write(self, buf)

    def change_name(self, name):
        self.display_name = None
        self.display_name = make_unique_name(name)

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
