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
import cmd
import os
from readline import get_current_history_length, get_history_item
from readline import add_history, clear_history
import sys
import tempfile
from fnmatch import fnmatch

from gsh.console import console_output
from gsh.stdin import the_stdin_thread
from gsh.host_syntax import expand_syntax
from gsh import dispatchers, remote_dispatcher

# The controlling shell, accessible with Ctrl-C
singleton = None

def make_singleton(options):
    """Prepate the control shell at initialization time"""
    global singleton
    singleton = control_shell(options)

def launch():
    """Ctrl-C was pressed"""
    return singleton.launch()

def toggle_shells(command, enable):
    """Enable or disable the specified shells"""
    for i in selected_shells(command):
        if i.active:
            i.set_enabled(enable)

def selected_shells(command):
    """Iterator over the shells with names matching the patterns.
    An empty patterns matches all the shells"""
    for pattern in (command or '*').split():
        found = False
        for expanded_pattern in expand_syntax(pattern):
            for i in dispatchers.all_instances():
                if fnmatch(i.display_name, expanded_pattern):
                    found = True
                    yield i
        if not found:
            print pattern, 'not found'

def complete_shells(text, line, predicate=lambda i: True):
    """Return the shell names to include in the completion"""
    res = [i.display_name + ' ' for i in dispatchers.all_instances() if \
                i.display_name.startswith(text) and \
                predicate(i) and \
                ' ' + i.display_name + ' ' not in line]
    return res

#
# This file descriptor is used to interrupt readline in raw_input().
# /dev/null is not enough as it does not get out of a 'Ctrl-R' reverse-i-search.
# A Ctrl-C seems to make raw_input() return in all cases, and avoids printing
# a newline
tempfile_fd, tempfile_name = tempfile.mkstemp()
os.remove(tempfile_name)
os.write(tempfile_fd, chr(3))

def interrupt_stdin_thread():
    """The stdin thread may be in raw_input(), get out of it"""
    if the_stdin_thread.ready_event.isSet():
        dupped_stdin = os.dup(0) # Backup the stdin fd
        assert not the_stdin_thread.wants_control_shell
        the_stdin_thread.wants_control_shell = True # Not user triggered
        os.lseek(tempfile_fd, 0, 0) # Rewind in the temp file
        os.dup2(tempfile_fd, 0) # This will make raw_input() return
        the_stdin_thread.interrupted_event.wait() # Wait for this return
        the_stdin_thread.wants_control_shell = False
        os.dup2(dupped_stdin, 0) # Restore stdin
        os.close(dupped_stdin) # Cleanup

def switch_readline_history(new_histo):
    """Alternate between the command line history from the remote shells (gsh)
    and the control shell"""
    xhisto_idx = xrange(1, get_current_history_length() + 1)
    prev_histo = map(get_history_item, xhisto_idx)
    clear_history()
    for line in new_histo:
        add_history(line)
    return prev_histo

class control_shell(cmd.Cmd):
    """The little command line brought when a SIGINT is received"""
    def __init__(self, options):
        cmd.Cmd.__init__(self)
        self.options = options
        self.prompt = '[ctrl]> '
        self.history = []

    def launch(self):
        if not self.options.interactive:
            # A Ctrl-C was issued in a non-interactive gsh => exit
            raise asyncore.ExitNow(1)
        self.stop = False
        interrupt_stdin_thread()
        gsh_histo = switch_readline_history(self.history)
        print ''
        console_output('')
        try:
            while True:
                try:
                    cmd.Cmd.cmdloop(self)
                except KeyboardInterrupt:
                    console_output('\n')
                else:
                    break
        finally:
            self.history = switch_readline_history(gsh_histo)
            console_output('\r')

    def completenames(self, text, *ignored):
        """Overriden to add the trailing space"""
        return [c + ' ' for c in cmd.Cmd.completenames(self, text, ignored)]

    # We do this just to have 'help' in the 'Documented commands'
    def do_help(self, command):
        """
        Usage: help [COMMAND]
        List available commands or show the documentation of a specific command.
        """
        return cmd.Cmd.do_help(self, command)

    def complete_list(self, text, line, begidx, endidx):
        return complete_shells(text, line)

    def do_list(self, command):
        """
        Usage: list [SHELLS...]
        List the specified or all remote shells and their states.
        The special characters * ? and [] work as expected.
        """
        nr_active = nr_dead = 0
        instances = []
        for i in selected_shells(command):
            instances.append(i.get_info())
            if i.active:
                nr_active += 1
            else:
                nr_dead += 1
        dispatchers.format_info(instances)
        print '%s\n\n%d active shells, %d dead shells, total: %d' % \
               ('\n'.join(instances), nr_active, nr_dead, nr_active + nr_dead)

    def do_continue(self, command):
        """
        Usage: continue
        Go back to gsh.
        """
        self.stop = True

    def do_EOF(self, command):
        """
        Usage: Ctrl-D
        Go back to gsh.
        """
        return self.do_continue(command)

    def do_quit(self, command):
        """
        Usage: quit
        Quit gsh.
        """
        raise asyncore.ExitNow(0)

    def complete_send_control(self, text, line, begidx, endidx):
        if line[len('send_control'):begidx].strip():
            # Control letter already given in command line
            return complete_shells(text, line, lambda i: i.enabled)
        if text in ('c', 'd', 'z'):
            return [text + ' ']
        return ['c', 'd', 'z']

    def do_send_control(self, command):
        """
        Usage: send_control LETTER [SHELLS...]
        Send a control character to the specified or all enabled shells.
        The first argument is the control character to send: c, d or z.
        The remaining optional arguments are the destination shells.
        The special characters * ? and [] work as expected.
        """
        splitted = command.split()
        if not splitted:
            print 'Expected at least a letter'
            return
        letter = splitted[0]
        if len(letter) != 1:
            print 'Expected a single letter, got:', letter
            return
        control_letter = chr(ord(letter.lower()) - ord('a') + 1)
        for i in selected_shells(' '.join(splitted[1:])):
            if i.enabled:
                i.dispatch_write(control_letter)

    def complete_enable(self, text, line, begidx, endidx):
        return complete_shells(text, line, lambda i: i.active and not i.enabled)

    def do_enable(self, command):
        """
        Usage: enable [SHELLS...]
        Enable sending commands to all or the specified shells.
        The special characters * ? and [] work as expected.
        """
        toggle_shells(command, True)

    def complete_disable(self, text, line, begidx, endidx):
        return complete_shells(text, line, lambda i: i.enabled)

    def do_disable(self, command):
        """
        Usage: disable [SHELLS...]
        Disable sending commands to all or the specified shells.
        The special characters * ? and [] work as expected.
        """
        toggle_shells(command, False)

    def complete_reconnect(self, text, line, begidx, endidx):
        return complete_shells(text, line, lambda i: not i.active)

    def do_reconnect(self, command):
        """
        Usage: reconnect [SHELLS...]
        Try to reconnect to all or the specified remote shells that have been
        disconnected.
        The special characters * ? and [] work as expected.
        """
        for i in selected_shells(command):
            if not i.active:
                i.reconnect()

    def do_add(self, command):
        """
        Usage: add NAMES...
        Add one or many remote shells.
        """
        for host in command.split():
            remote_dispatcher.remote_dispatcher(self.options, host)

    def complete_delete_disabled(self, text, line, begidx, endidx):
        return complete_shells(text, line, lambda i: not i.enabled)

    def do_delete_disabled(self, command):
        """
        Usage: delete_disabled [SHELLS...]
        Delete the specified or all remote processes that are disabled,
        in order to have a shorter list.
        The special characters * ? and [] work as expected.
        """
        to_delete = []
        for i in selected_shells(command):
            if not i.enabled:
                to_delete.append(i)
        for i in to_delete:
            i.disconnect()
            i.close()

    def do_rename(self, command):
        """
        Usage: rename [NEW_NAME]
        Rename all enabled remote processes with the argument. The argument will
        be shell expanded on the remote processes. With no argument, the
        original hostname will be restored as the displayed name.
        """
        for i in dispatchers.all_instances():
            if i.enabled:
                i.rename(command)

    def complete_set_debug(self, text, line, begidx, endidx):
        if line[len('set_debug'):begidx].strip():
            # Control letter already given in command line
            return complete_shells(text, line)
        if text in ('y', 'n'):
            return [text + ' ']
        return ['y', 'n']

    def do_set_debug(self, command):
        """
        Usage: set_debug y|n [SHELLS...]
        Enable or disable debugging output for all or the specified shells.
        The first argument is 'y' to enable the debugging output, 'n' to
        disable it.
        The remaining optional arguments are the selected shells.
        The special characters * ? and [] work as expected.
        """
        splitted = command.split()
        if not splitted:
            print 'Expected at least a letter'
            return
        letter = splitted[0].lower()
        if letter not in ('y', 'n'):
            print "Expected 'y' or 'n', got:", splitted[0]
            return
        debug = letter == 'y'
        for i in selected_shells(' '.join(splitted[1:])):
            i.debug = debug

    def postcmd(self, stop, line):
        return self.stop

    def emptyline(self):
        pass
