import asyncore
import os
import pty
import random
import sys

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
    for i in asyncore.socket_map.itervalues():
        if isinstance(i, remote_dispatcher):
            yield i

def count_completed_processes():
    completed_processes = 0
    total = 0
    for i in all_instances():
        if i.enabled:
            total += 1
            if i.state == STATE_IDLE:
                completed_processes += 1
    return completed_processes, total

def all_terminated():
    for i in all_instances():
        if i.enabled and i.state != STATE_TERMINATED:
            return False
    return True

def format_info(info_list):
    info_list.sort(key=lambda i:int(i[1][3:]))
    max_lengths = []
    for i in xrange(len(info_list[0])):
        max_lengths.append(max([len(str(info[i])) for info in info_list]))
    for info_id in xrange(len(info_list)):
        info = info_list[info_id]
        for str_id in xrange(len(info)):
            orig_str = str(info[str_id])
            indent = max_lengths[str_id] - len(orig_str)
            info[str_id] = orig_str + indent * ' '
        info_list[info_id] = " ".join(info)

class remote_dispatcher(buffered_dispatcher):
    """A remote_dispatcher is a ssh process we communicate with"""

    def __init__(self, options, name):
        self.pid, fd = pty.fork()
        if self.pid == 0:
            # Child
            self.launch_ssh(options, name)
            sys.exit(1)
        # Parent
        buffered_dispatcher.__init__(self, fd, name)

        self.active = True # deactived shells are dead forever
        self.enabled = True # shells can be enabled and disabled
        self.options = options
        if options.log_dir:
            # Open the log file
            log_path = os.path.join(options.log_dir, name.replace('/', '_'))
            self.log_file = os.open(log_path, os.O_WRONLY|os.O_CREAT, 0644)
            os.ftruncate(self.log_file, 0)
        else:
            self.log_file = None

        self.state = STATE_NOT_STARTED
        self.termination = None
        self.set_prompt()
        if options.command:
            self.dispatch_write(options.command + '\n')
            self.dispatch_termination()
            self.options.interactive = False
        else:
            self.options.interactive = sys.stdin.isatty()

    def launch_ssh(self, options, name):
        if options.ssh_shell_cmd:
            shell = os.environ.get('SHELL', '/bin/sh')
            exec_args = (shell, '-c', '%s %s' % (options.ssh_shell_cmd, name))
        else:
            exe = options.ssh_exec or 'ssh'
            exec_args = (exe, name)
        os.execlp(exec_args[0], *exec_args)

    def change_state(self, state):
        self.log('state => %s\n' % (STATE_NAMES[state]), debug=True)
        self.state = state

    def disconnect(self):
        self.read_buffer = ''
        self.write_buffer = ''
        self.active = False
        self.enabled = False
        if self.options.abort_error:
            raise asyncore.ExitNow

    def dispatch_termination(self):
        if not self.termination:
            term1 = '[gsh termination ' + str(random.random())[2:]
            term2 = str(random.random())[2:] + ']'
            self.termination = term1 + term2
            self.dispatch_write('echo "%s""%s"\n' % (term1, term2))
            if self.state != STATE_NOT_STARTED:
                self.change_state(STATE_EXPECTING_NEXT_LINE)

    def set_prompt(self):
        # No right prompt
        self.dispatch_write('RPS1=\n')
        self.dispatch_write('RPROMPT=\n')
        self.dispatch_write('TERM=ansi\n')
        prompt1 = '[gsh prompt ' + str(random.random())[2:]
        prompt2 = str(random.random())[2:] + ']'
        self.prompt = prompt1 + prompt2
        self.dispatch_write('PS1="%s""%s\n"\n' % (prompt1, prompt2))

    def readable(self):
        # When self.active is set to False we are no more interested in reading
        return self.active

    def handle_error(self):
        if buffered_dispatcher.handle_error(self):
            console_output('Error talking to %s\n ' % (self.name), sys.stderr)
            self.disconnect()

    def handle_read(self):
        """We got some output from a remote shell"""
        if not self.active:
            return
        try:
            new_data = buffered_dispatcher.handle_read(self)
        except buffered_dispatcher.BufferTooLarge:
            console_output('%s: read buffer too large\n' % (self.name),
                           sys.stderr)
            self.disconnect()
            return
        self.log('==> ' + new_data, debug=True)
        lf_pos = new_data.find('\n')
        if lf_pos >= 0:
            # Optimization: we knew there were no '\n' in the previous read
            # buffer, so we searched only in the new_data and we offset the
            # found index by the length of the previous buffer
            lf_pos += len(self.read_buffer) - len(new_data)
        limit = buffered_dispatcher.MAX_BUFFER_SIZE / 10
        if lf_pos < 0 and len(self.read_buffer) > limit:
            lf_pos = limit
        while lf_pos >= 0:
            line = self.read_buffer[:lf_pos]
            if self.prompt in line:
                if self.options.interactive:
                    self.change_state(STATE_IDLE)
                else:
                    self.change_state(STATE_EXPECTING_NEXT_LINE)
            elif self.termination and self.termination in line:
                self.change_state(STATE_TERMINATED)
                self.disconnect()
            elif self.state == STATE_EXPECTING_NEXT_LINE:
                self.change_state(STATE_EXPECTING_LINE)
            elif self.state != STATE_NOT_STARTED:
                self.log(line + '\n')
                if not self.options.print_first or \
                   self.state == STATE_EXPECTING_LINE:
                    console_output(self.name + ': ' + line + '\n')
                    self.change_state(STATE_RUNNING)

            # Go to the next line in the buffer
            self.read_buffer = self.read_buffer[lf_pos + 1:]
            lf_pos = self.read_buffer.find('\n')

    def writable(self):
        return self.active and buffered_dispatcher.writable(self)

    def log(self, buf, debug=False):
        if self.log_file is None:
            if debug and self.options.debug:
                state = STATE_NAMES[self.state]
                console_output('[dbg] %s[%s]: %s' % (self.name, state, buf))
        else:
            if (not debug) == (not self.options.debug):
                os.write(self.log_file, buf)

    def get_info(self):
        if self.active:
            state = STATE_NAMES[self.state]
        else:
            state = ''

        return [self.name, 'fd:%d' % (self.fd),
                'r:%d' % (len(self.read_buffer)),
                'w:%d' % (len(self.write_buffer)),
                'active:%s' % (str(self.active)),
                'enabled:%s' % (str(self.enabled)), state]

    def dispatch_write(self, buf):
        if self.active and self.enabled:
            self.log('<== ' + buf, debug=True)
            try:
                buffered_dispatcher.dispatch_write(self, buf)
            except buffered_dispatcher.BufferTooLarge:
                console_output('%s: write buffer too large\n' % (self.name),
                               sys.stderr)
                self.disconnect()
