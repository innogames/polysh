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
import sys
import tempfile
from fnmatch import fnmatch
import readline

from gsh.console import console_output
from gsh.stdin import the_stdin_thread
from gsh.host_syntax import expand_syntax
from gsh import dispatchers, remote_dispatcher

def toggle_shells(command, enable):
    """Enable or disable the specified shells"""
    for i in selected_shells(command):
        if i.active:
            i.set_enabled(enable)

def selected_shells(command):
    """Iterator over the shells with names matching the patterns.
    An empty patterns matches all the shells"""
    selected = set()
    for pattern in (command or '*').split():
        found = False
        for expanded_pattern in expand_syntax(pattern):
            for i in dispatchers.all_instances():
                if fnmatch(i.display_name, expanded_pattern):
                    found = True
                    if i not in selected:
                        selected.add(i)
                        yield i
        if not found:
            print pattern, 'not found'

def complete_shells(line, text, predicate=lambda i: True):
    """Return the shell names to include in the completion"""
    res = [i.display_name for i in dispatchers.all_instances() if \
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

def list_control_commands():
    import gsh.control_commands
    return [c[3:] for c in dir(gsh.control_commands) if c.startswith('do_')]

def get_control_command(name):
    import gsh.control_commands
    func = getattr(gsh.control_commands, 'do_' + name)
    return func

def complete_control_command(line, text):
    import gsh.control_commands
    if readline.get_begidx() == 0:
        # Completing control command name
        cmds = list_control_commands()
        prefix = text[1:]
        matches = [':' + cmd for cmd in cmds if cmd.startswith(prefix)]
    else:
        # Completing control command parameters
        cmd = line.split()[0][1:]
        def_compl = lambda line: []
        compl_func = getattr(gsh.control_commands, 'complete_' + cmd, def_compl)
        matches = compl_func(line, text)
    return matches

def handle_control_command(line):
    cmd_name = line.split()[0]
    try:
        cmd_func = get_control_command(cmd_name)
    except AttributeError:
        print 'Unknown control command:', cmd_name
    else:
        parameters = line[len(cmd_name) + 1:]
        cmd_func(parameters)

