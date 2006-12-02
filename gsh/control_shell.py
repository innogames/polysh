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

import cmd
import os
import sys
import termios
from fnmatch import fnmatch

from gsh.console import set_blocking_stdin
from gsh.stdin import the_stdin_thread
from gsh import remote_dispatcher

# The controlling shell, accessible with Ctrl-C
singleton = None

def make_singleton(options):
    global singleton
    singleton = control_shell(options)

def launch():
    return singleton.launch()

def send_termios_char(char):
    for i in remote_dispatcher.all_instances():
        c = termios.tcgetattr(i.fd)[6][char]
        i.dispatch_write(c)

def toggle_shells(command, enable):
    for i in selected_shells(command):
        if i.active:
            i.enabled = enable

def selected_shells(command):
    for pattern in command.split():
        found = False
        for i in remote_dispatcher.all_instances():
            if fnmatch(i.name, pattern):
                found = True
                yield i
        if not found:
            print pattern, 'not found'

def complete_shells(text, line, predicate):
    given = line.split()[1:]
    res = [i.name for i in remote_dispatcher.all_instances() if \
                i.name.startswith(text) and \
                predicate(i) and \
                i.name not in given]
    return res

def interrupt_stdin_thread():
    if the_stdin_thread.ready_event.isSet():
        dupped_stdin = os.dup(0)
        null_fd = os.open('/dev/null', os.O_RDONLY)
        assert not the_stdin_thread.wants_control_shell
        the_stdin_thread.wants_control_shell = True
        os.dup2(null_fd, 0)
        the_stdin_thread.interrupted_event.wait()
        the_stdin_thread.wants_control_shell = False
        os.dup2(dupped_stdin, 0)

class control_shell(cmd.Cmd):
    """The little command line brought when a SIGINT is received"""
    def __init__(self, options):
        cmd.Cmd.__init__(self)
        self.options = options
        self.prompt = '[ctrl]> '

    def launch(self):
        if not self.options.interactive:
            # A Ctrl-C was issued in a non-interactive gsh => exit
            sys.exit(1)
        self.stop = False
        interrupt_stdin_thread()
        set_blocking_stdin(True)
        try:
            while True:
                try:
                    cmd.Cmd.cmdloop(self, '\n')
                except KeyboardInterrupt:
                    pass
                else:
                    break
        finally:
            set_blocking_stdin(False)

    # We do this just to have 'help' in the 'Documented commands'
    def do_help(self, command):
        """
        List available commands
        """
        return cmd.Cmd.do_help(self, command)

    def do_list(self, command):
        """
        List all remote shells and their states
        """
        nr_active = nr_dead = 0
        instances = []
        for i in remote_dispatcher.all_instances():
            instances.append(i.get_info())
            if i.active:
                nr_active += 1
            else:
                nr_dead += 1
        remote_dispatcher.format_info(instances)
        print '%s\n\n%d active shells, %d dead shells, total: %d' % \
               ('\n'.join(instances), nr_active, nr_dead, nr_active + nr_dead)

    def do_continue(self, command):
        """
        Go back to gsh
        """
        self.stop = True

    def do_EOF(self, command):
        """
        Go back to gsh
        """
        return self.do_continue(command)

    def do_quit(self, command):
        """
        Quit gsh
        """
        sys.exit(0)

    def do_get_print_first(self, command):
        """
        Check whether we only print the first line for each command output
        """
        print 'print_first = ' + str(not not self.options.print_first)

    def do_set_print_first(self, command):
        """
        Print only the first line for each command output
        """
        self.options.print_first = True

    def do_unset_print_first(self, command):
        """
        Print all lines for each command output
        """
        self.options.print_first = False

    def do_send_sigint(self, command):
        """
        Send a Ctrl-C to all remote shells
        """
        send_termios_char(termios.VINTR)

    def do_send_eof(self, command):
        """
        Send a Ctrl-D to all remote shells
        """
        send_termios_char(termios.VEOF)

    def do_send_sigtstp(self, command):
        """
        Send a Ctrl-Z to all remote shells
        """
        send_termios_char(termios.VSUSP)

    def complete_enable(self, text, line, begidx, endidx):
        return complete_shells(text, line, lambda i: i.active and not i.enabled)

    def do_enable(self, command):
        """
        Enable sending commands to the specified shells
        * ? and [] work as expected
        """
        toggle_shells(command, True)

    def complete_disable(self, text, line, begidx, endidx):
        return complete_shells(text, line, lambda i: i.active and i.enabled)

    def do_disable(self, command):
        """
        Disable sending commands to the specified shells
        * ? and [] work as expected
        """
        toggle_shells(command, False)

    def complete_reconnect(self, text, line, begidx, endidx):
        return complete_shells(text, line, lambda i: not i.active)

    def do_reconnect(self, command):
        """
        Try to reconnect to the specified remote shells that have been
        disconnected
        """
        for i in selected_shells(command):
            if not i.active:
                i.reconnect()

    def postcmd(self, stop, line):
        return self.stop

    def emptyline(self):
        pass
