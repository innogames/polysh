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
# Copyright (c) 2006, 2007, 2008 Guillaume Chazarain <guichaz@yahoo.fr>

import asyncore
import os
import sys
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
    instance_found = False
    for pattern in (command or '*').split():
        found = False
        for expanded_pattern in expand_syntax(pattern):
            for i in dispatchers.all_instances():
                instance_found = True
                if fnmatch(i.display_name, expanded_pattern):
                    found = True
                    if i not in selected:
                        selected.add(i)
                        yield i
        if instance_found and not found:
            print pattern, 'not found'

def complete_shells(line, text, predicate=lambda i: True):
    """Return the shell names to include in the completion"""
    res = [i.display_name + ' ' for i in dispatchers.all_instances() if \
                i.display_name.startswith(text) and \
                predicate(i) and \
                ' ' + i.display_name + ' ' not in line]
    return res

def expand_local_path(path):
    return os.path.expanduser(os.path.expandvars(path) or '~')

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
        matches = [':' + cmd + ' ' for cmd in cmds if cmd.startswith(prefix)]
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

