"""Polysh - Helpers for Control Commands

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

import os
from fnmatch import fnmatch
import readline
from typing import Iterator, List, Set, Callable

from polysh.host_syntax import expand_syntax
from polysh.console import console_output
from polysh import dispatchers
from polysh import remote_dispatcher


def toggle_shells(command: str, enable: bool) -> None:
    """Enable or disable the specified shells. If the command would have
    no effect, it changes all other shells to the inverse enable value."""
    selection = list(selected_shells(command))
    if command and command != '*' and selection:
        for i in selection:
            if i.state != remote_dispatcher.STATE_DEAD and i.enabled != enable:
                break
        else:
            toggle_shells('*', not enable)

    for i in selection:
        if i.state != remote_dispatcher.STATE_DEAD:
            i.set_enabled(enable)


def selected_shells(
    command: str
) -> Iterator[remote_dispatcher.RemoteDispatcher]:
    """Iterator over the shells with names matching the patterns.
    An empty patterns matches all the shells"""
    if not command or command == '*':
        for i in dispatchers.all_instances():
            yield i
        return
    selected = set()  # type: Set[remote_dispatcher.RemoteDispatcher]
    instance_found = False
    for pattern in command.split():
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
            console_output('{} not found\n'.format(pattern).encode())


def complete_shells(
        line: str, text: str,
        predicate: Callable = lambda i: True) -> List[str]:
    """Return the shell names to include in the completion"""
    res = [i.display_name + ' ' for i in dispatchers.all_instances() if
           i.display_name.startswith(text) and
           predicate(i) and
           ' ' + i.display_name + ' ' not in line]
    return res


def expand_local_path(path: str) -> str:
    return os.path.expanduser(os.path.expandvars(path) or '~')


def list_control_commands() -> List[str]:
    from polysh import control_commands
    return [c[3:] for c in dir(control_commands) if c.startswith('do_')]


def get_control_command(name: str) -> Callable:
    from polysh import control_commands
    func = getattr(control_commands, 'do_' + name)
    return func


def complete_control_command(line: str, text: str) -> List[str]:
    from polysh import control_commands
    if readline.get_begidx() == 0:
        # Completing control command name
        cmds = list_control_commands()
        prefix = text[1:]
        matches = [':' + cmd + ' ' for cmd in cmds if cmd.startswith(prefix)]
    else:
        # Completing control command parameters
        cmd = line.split()[0][1:]

        def def_compl(line: str) -> List:
            return []
        compl_func = getattr(control_commands, 'complete_' + cmd, def_compl)
        matches = compl_func(line, text)
    return matches


def handle_control_command(line: str) -> None:
    if not line:
        return
    cmd_name = line.split()[0]
    try:
        cmd_func = get_control_command(cmd_name)
    except AttributeError:
        console_output(
            'Unknown control command: {}\n'.format(cmd_name).encode())
    else:
        parameters = line[len(cmd_name) + 1:]
        cmd_func(parameters)
