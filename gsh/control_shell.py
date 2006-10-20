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
import sys
import termios

from gsh.console import set_stdin_blocking

# The controlling shell, accessible with Ctrl-C
singleton = None

def make_singleton(options):
    global singleton
    singleton = control_shell(options)

def launch():
    return singleton.launch()

def send_termios_char(char):
    from gsh import remote_dispatcher
    for i in remote_dispatcher.all_instances():
        c = termios.tcgetattr(i.fd)[6][char]
        i.dispatch_write(c)

def toggle_shells(command, enable):
    from gsh import remote_dispatcher
    for name in command.split():
        if name == '*':
            for i in remote_dispatcher.all_instances():
                if i.active:
                    i.enabled = enable
        else:
            for i in remote_dispatcher.all_instances():
                if name == i.name:
                    if not i.active:
                        print name, 'is not active'
                    elif i.enabled == enable:
                        print 'nothing to do for', name
                    else:
                        i.enabled = enable
                    break
            else:
                print name, 'not found'

def complete_toggle_shells(text, line, enable):
    from gsh import remote_dispatcher
    given = line.split()[1:]
    if '*' in given:
        # No more completion as 'all' shells have been selected
        return []
    res = [i.name for i in remote_dispatcher.all_instances() if \
                i.active and \
                i.name.startswith(text) and \
                i.enabled != enable and \
                i.name not in given]
    if not text:
        # Show '*' only if the argument to complete is still empty
        res += ['*']
    return res

class control_shell(cmd.Cmd):
    """The little command line brought when a SIGINT is received"""
    def __init__(self, options):
        cmd.Cmd.__init__(self)
        self.options = options

    def launch(self):
        if not self.options.interactive:
            # A Ctrl-C was issued in a non-interactive gsh => exit
            sys.exit(1)
        self.stop = False
        set_stdin_blocking(True)
        intro = sys.argv[0] + ' command line'
        while True:
            try:
                cmd.Cmd.cmdloop(self, intro)
            except KeyboardInterrupt:
                pass
            else:
                return
        set_stdin_blocking(False)

    # We do this just to have 'help' in the 'Documented commands'
    def do_help(self, command):
        """List available commands"""
        return cmd.Cmd.do_help(self, command)

    def do_list(self, command):
        """List all remote shells and their states"""
        from gsh import remote_dispatcher
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
        """Go back to gsh"""
        self.stop = True

    def do_EOF(self, command):
        """Go back to gsh"""
        return self.do_continue(command)

    def do_quit(self, command):
        """Quit gsh"""
        sys.exit(0)

    def do_get_print_first(self, command):
        """Check whether we only print the first line for each command output"""
        print 'print_first = ' + str(not not self.options.print_first)

    def do_set_print_first(self, command):
        """Print only the first line for each command output"""
        self.options.print_first = True

    def do_unset_print_first(self, command):
        """Print all lines for each command output"""
        self.options.print_first = False

    def do_send_sigint(self, command):
        """Send a Ctrl-C to all remote shells"""
        send_termios_char(termios.VINTR)

    def do_send_eof(self, command):
        """Send a Ctrl-D to all remote shells"""
        send_termios_char(termios.VEOF)

    def do_send_sigtstp(self, command):
        """Send a Ctrl-Z to all remote shells"""
        send_termios_char(termios.VSUSP)

    def complete_enable(self, text, line, begidx, endidx):
        return complete_toggle_shells(text, line, True)

    def do_enable(self, command):
        """Enable sending commands to the specified shells, * for all shells"""
        toggle_shells(command, True)

    def complete_disable(self, text, line, begidx, endidx):
        return complete_toggle_shells(text, line, False)

    def do_disable(self, command):
        """Disable sending commands to the specified shells, * for all shells"""
        toggle_shells(command, False)

    def postcmd(self, stop, line):
        return self.stop

    def emptyline(self):
        pass
