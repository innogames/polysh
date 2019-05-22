"""Polysh - Control Commands

The control commands are documented on the README.

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
import shlex
from typing import List

from polysh.control_commands_helpers import (
    complete_shells,
    expand_local_path,
    selected_shells,
    toggle_shells,
)
from polysh.completion import complete_local_path, add_to_history
from polysh.console import console_output
from polysh import dispatchers
from polysh import remote_dispatcher
from polysh import stdin


def complete_list(line: str, text: str) -> List[str]:
    return complete_shells(line, text)


def do_list(command: str) -> None:
    instances = [i.get_info() for i in selected_shells(command)]
    flat_instances = dispatchers.format_info(instances)
    console_output(b''.join(flat_instances))


def do_quit(command: str) -> None:
    raise asyncore.ExitNow(0)


def complete_chdir(line: str, text: str) -> List[str]:
    return list(filter(os.path.isdir, complete_local_path(text)))


def do_chdir(command: str) -> None:
    try:
        os.chdir(expand_local_path(command.strip()))
    except OSError as e:
        console_output('{}\n'.format(str(e)).encode())


def complete_send_ctrl(line: str, text: str) -> List[str]:
    if len(line[:-1].split()) >= 2:
        # Control letter already given in command line
        return complete_shells(line, text, lambda i: i.enabled)
    if text in ('c', 'd', 'z'):
        return [text + ' ']
    return ['c ', 'd ', 'z ']


def do_send_ctrl(command: str) -> None:
    split = command.split()
    if not split:
        console_output(b'Expected at least a letter\n')
        return
    letter = split[0]
    if len(letter) != 1:
        console_output('Expected a single letter, got: {}\n'.format(
            letter).encode())
        return
    control_letter = chr(ord(letter.lower()) - ord('a') + 1)
    for i in selected_shells(' '.join(split[1:])):
        if i.enabled:
            i.dispatch_write(control_letter.encode())


def complete_reset_prompt(line: str, text: str) -> List[str]:
    return complete_shells(line, text, lambda i: i.enabled)


def do_reset_prompt(command: str) -> None:
    for i in selected_shells(command):
        i.dispatch_command(i.init_string)


def complete_enable(line: str, text: str) -> List[str]:
    return complete_shells(line, text, lambda i:
                           i.state != remote_dispatcher.STATE_DEAD)


def do_enable(command: str) -> None:
    toggle_shells(command, True)


def complete_disable(line: str, text: str) -> List[str]:
    return complete_shells(line, text, lambda i:
                           i.state != remote_dispatcher.STATE_DEAD)



def do_disable(command: str) -> None:
    toggle_shells(command, False)


def complete_reconnect(line: str, text: str) -> List[str]:
    return complete_shells(line, text, lambda i:
                           i.state == remote_dispatcher.STATE_DEAD)


def do_reconnect(command: str) -> None:
    selec = selected_shells(command)
    to_reconnect = [i for i in selec if i.state ==
                    remote_dispatcher.STATE_DEAD]
    for i in to_reconnect:
        i.disconnect()
        i.close()

    hosts = [i.hostname for i in to_reconnect]
    dispatchers.create_remote_dispatchers(hosts)


def do_add(command: str) -> None:
    dispatchers.create_remote_dispatchers(command.split())


def complete_purge(line: str, text: str) -> List[str]:
    return complete_shells(line, text, lambda i: not i.enabled)


def do_purge(command: str) -> None:
    to_delete = []
    for i in selected_shells(command):
        if not i.enabled:
            to_delete.append(i)
    for i in to_delete:
        i.disconnect()
        i.close()


def do_rename(command: str) -> None:
    for i in dispatchers.all_instances():
        if i.enabled:
            i.rename(command.encode())


def do_hide_password(command: str) -> None:
    warned = False
    for i in dispatchers.all_instances():
        if i.enabled and i.debug:
            i.debug = False
            if not warned:
                console_output(b'Debugging disabled to avoid displaying '
                               b'passwords\n')
                warned = True
    stdin.set_echo(False)

    if remote_dispatcher.options.log_file:
        console_output(b'Logging disabled to avoid writing passwords\n')
        remote_dispatcher.options.log_file = None


def complete_set_debug(line: str, text: str) -> List[str]:
    if len(line[:-1].split()) >= 2:
        # Debug value already given in command line
        return complete_shells(line, text)
    if text.lower() in ('y', 'n'):
        return [text + ' ']
    return ['y ', 'n ']


def do_set_debug(command: str) -> None:
    split = command.split()
    if not split:
        console_output(b'Expected at least a letter\n')
        return
    letter = split[0].lower()
    if letter not in ('y', 'n'):
        console_output("Expected 'y' or 'n', got: {}\n".format(
            split[0]).encode())
        return
    debug = letter == 'y'
    for i in selected_shells(' '.join(split[1:])):
        i.debug = debug


def do_export_vars(command: str) -> None:
    rank = 0
    for shell in dispatchers.all_instances():
        if shell.enabled:
            environment_variables = {
                'POLYSH_RANK': str(rank),
                'POLYSH_NAME': shell.hostname,
                'POLYSH_DISPLAY_NAME': shell.display_name,
            }
            for name, value in environment_variables.items():
                shell.dispatch_command('export {}={}\n'.format(
                    name, shlex.quote(value)).encode())
            rank += 1

    for shell in dispatchers.all_instances():
        if shell.enabled:
            shell.dispatch_command('export POLYSH_NR_SHELLS={:d}\n'.format(
                rank).encode())


add_to_history('$POLYSH_RANK $POLYSH_NAME $POLYSH_DISPLAY_NAME')
add_to_history('$POLYSH_NR_SHELLS')


def complete_set_log(line: str, text: str) -> List[str]:
    return complete_local_path(text)


def do_set_log(command: str) -> None:
    command = command.strip()
    if command:
        try:
            remote_dispatcher.options.log_file = open(command, 'a')
        except IOError as e:
            console_output('{}\n'.format(str(e)).encode())
            command = None
    if not command:
        remote_dispatcher.options.log_file = None
        console_output(b'Logging disabled\n')


def complete_show_read_buffer(line: str, text: str) -> List[str]:
    return complete_shells(line, text, lambda i: i.read_buffer or
                           i.read_in_state_not_started)


def do_show_read_buffer(command: str) -> None:
    for i in selected_shells(command):
        if i.read_in_state_not_started:
            i.print_lines(i.read_in_state_not_started)
            i.read_in_state_not_started = b''
