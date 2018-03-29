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
# Copyright (c) 2006 Guillaume Chazarain <guichaz@gmail.com>

import asyncore
import os
import pipes
import shutil
import sys
import tempfile

from polysh.control_commands_helpers import complete_shells, selected_shells
from polysh.control_commands_helpers import list_control_commands
from polysh.control_commands_helpers import get_control_command, toggle_shells
from polysh.control_commands_helpers import expand_local_path
from polysh.completion import complete_local_path, add_to_history
from polysh.console import console_output
from polysh.version import VERSION
from polysh import dispatchers
from polysh import remote_dispatcher
from polysh import stdin


def complete_help(line, text):
    colon = text.startswith(':')
    text = text.lstrip(':')
    res = [cmd + ' ' for cmd in list_control_commands() if
           cmd.startswith(text) and ' ' + cmd + ' ' not in line]
    if colon:
        res = [':' + cmd for cmd in res]
    return res


def do_help(command):
    """
    Usage: :help [COMMAND]
    List control commands or show their documentations.
    """
    command = command.strip()
    if command:
        texts = []
        for name in command.split():
            try:
                doc = get_control_command(name.lstrip(':')).__doc__
            except AttributeError:
                console_output('Unknown control command: %s\n' % name)
            else:
                doc_lines = [d.strip() for d in doc.split('\n') if d.strip()]
                texts.append('\n'.join(doc_lines))
        if texts:
            console_output('\n\n'.join(texts))
            console_output('\n')
    else:
        names = list_control_commands()
        max_name_len = max(list(map(len, names)))
        for i in range(len(names)):
            name = names[i]
            txt = ':' + name + (max_name_len - len(name) + 2) * ' '
            doc = get_control_command(name).__doc__
            txt += doc.split('\n')[2].strip() + '\n'
            console_output(txt)


def complete_list(line, text):
    return complete_shells(line, text)


def do_list(command):
    """
    Usage: :list [SHELLS...]
    List remote shells and their states.
    The output consists of: <hostname> <enabled?> <state>: <last printed line>.
    The special characters * ? and [] work as expected.
    """
    instances = [i.get_info() for i in selected_shells(command)]
    flat_instances = dispatchers.format_info(instances)
    console_output(''.join(flat_instances))


def do_quit(command):
    """
    Usage: :quit
    Quit polysh.
    """
    raise asyncore.ExitNow(0)


def complete_chdir(line, text):
    return list(filter(os.path.isdir, complete_local_path(text)))


def do_chdir(command):
    """
    Usage: :chdir LOCAL_PATH
    Change the current directory of polysh (not the remote shells).
    """
    try:
        os.chdir(expand_local_path(command.strip()))
    except OSError as e:
        console_output('%s\n' % str(e))


def complete_send_ctrl(line, text):
    if len(line[:-1].split()) >= 2:
        # Control letter already given in command line
        return complete_shells(line, text, lambda i: i.enabled)
    if text in ('c', 'd', 'z'):
        return [text + ' ']
    return ['c ', 'd ', 'z ']


def do_send_ctrl(command):
    """
    Usage: :send_ctrl LETTER [SHELLS...]
    Send a control character to remote shells.
    The first argument is the control character to send like c, d or z.
    Note that these three control characters can be sent simply by typing them
    into polysh.
    The remaining optional arguments are the destination shells.
    The special characters * ? and [] work as expected.
    """
    split = command.split()
    if not split:
        console_output('Expected at least a letter\n')
        return
    letter = split[0]
    if len(letter) != 1:
        console_output('Expected a single letter, got: %s\n' % letter)
        return
    control_letter = chr(ord(letter.lower()) - ord('a') + 1)
    for i in selected_shells(' '.join(split[1:])):
        if i.enabled:
            i.dispatch_write(control_letter.encode())


def complete_reset_prompt(line, text):
    return complete_shells(line, text, lambda i: i.enabled)


def do_reset_prompt(command):
    """
    Usage: :reset_prompt [SHELLS...]
    Change the prompt to be recognized by polysh.
    The special characters * ? and [] work as expected.
    """
    for i in selected_shells(command):
        i.dispatch_command(i.init_string)


def complete_enable(line, text):
    return complete_shells(line, text, lambda i:
                           i.state != remote_dispatcher.STATE_DEAD)


def do_enable(command):
    """
    Usage: :enable [SHELLS...]
    Enable sending commands to remote shells.
    If the command would have no effect, it changes all other shells to the
    inverse enable value. That is, if you enable only already enabled
    shells, it will first disable all other shells.
    The special characters * ? and [] work as expected.
    """
    toggle_shells(command, True)


def complete_disable(line, text):
    return complete_shells(line, text, lambda i:
                           i.state != remote_dispatcher.STATE_DEAD)


def do_disable(command):
    """
    Usage: :disable [SHELLS...]
    Disable sending commands to remote shells.
    If the command would have no effect, it changes all other shells to the
    inverse enable value. That is, if you disable only already disabled
    shells, it will first enable all other shells.
    The special characters * ? and [] work as expected.
    """
    toggle_shells(command, False)


def complete_reconnect(line, text):
    return complete_shells(line, text, lambda i:
                           i.state == remote_dispatcher.STATE_DEAD)


def do_reconnect(command):
    """
    Usage: :reconnect [SHELLS...]
    Try to reconnect to disconnected remote shells.
    The special characters * ? and [] work as expected.
    """
    selec = selected_shells(command)
    to_reconnect = [i for i in selec if i.state ==
                    remote_dispatcher.STATE_DEAD]
    for i in to_reconnect:
        i.disconnect()
        i.close()

    hosts = [i.hostname for i in to_reconnect]
    dispatchers.create_remote_dispatchers(hosts)


def do_add(command):
    """
    Usage: :add NAMES...
    Add one or many remote shells.
    """
    dispatchers.create_remote_dispatchers(command.split())


def complete_purge(line, text):
    return complete_shells(line, text, lambda i: not i.enabled)


def do_purge(command):
    """
    Usage: :purge [SHELLS...]
    Delete disabled remote shells.
    This helps to have a shorter list.
    The special characters * ? and [] work as expected.
    """
    to_delete = []
    for i in selected_shells(command):
        if not i.enabled:
            to_delete.append(i)
    for i in to_delete:
        i.disconnect()
        i.close()


def do_rename(command):
    """
    Usage: :rename [NEW_NAME]
    Rename all enabled remote shells with the argument.
    The argument will be shell expanded on the remote processes. With no
    argument, the original hostname will be restored as the displayed name.
    """
    for i in dispatchers.all_instances():
        if i.enabled:
            i.rename(command)


def do_hide_password(command):
    """
    Usage: :hide_password
    Do not echo the next typed line.
    This is useful when entering password. If debugging or logging is enabled,
    it will be disabled to avoid displaying a password. Therefore, you will have
    to reenable logging or debugging afterwards if need be.
    """
    warned = False
    for i in dispatchers.all_instances():
        if i.enabled and i.debug:
            i.debug = False
            if not warned:
                console_output('Debugging disabled to avoid displaying '
                               'passwords\n')
                warned = True
    stdin.set_echo(False)

    if remote_dispatcher.options.log_file:
        console_output('Logging disabled to avoid writing passwords\n')
        remote_dispatcher.options.log_file = None


def complete_set_debug(line, text):
    if len(line[:-1].split()) >= 2:
        # Debug value already given in command line
        return complete_shells(line, text)
    if text.lower() in ('y', 'n'):
        return [text + ' ']
    return ['y ', 'n ']


def do_set_debug(command):
    """
    Usage: :set_debug y|n [SHELLS...]
    Enable or disable debugging output for remote shells.
    The first argument is 'y' to enable the debugging output, 'n' to
    disable it.
    The remaining optional arguments are the selected shells.
    The special characters * ? and [] work as expected.
    """
    split = command.split()
    if not split:
        console_output('Expected at least a letter\n')
        return
    letter = split[0].lower()
    if letter not in ('y', 'n'):
        console_output("Expected 'y' or 'n', got: %s\n" % split[0])
        return
    debug = letter == 'y'
    for i in selected_shells(' '.join(split[1:])):
        i.debug = debug


def do_export_vars(command):
    """
    Usage: :export_vars
    Export some environment variables on enabled remote shells.
    POLYSH_NR_SHELLS is the total number of enabled shells. POLYSH_RANK uniquely
    identifies each shell with a number between 0 and POLYSH_NR_SHELLS - 1.
    POLYSH_NAME is the hostname as specified on the command line and
    POLYSH_DISPLAY_NAME the hostname as displayed by :list (most of the time the
    same as POLYSH_NAME).
    """
    rank = 0
    for shell in dispatchers.all_instances():
        if shell.enabled:
            environment_variables = {
                'POLYSH_RANK': rank,
                'POLYSH_NAME': shell.hostname,
                'POLYSH_DISPLAY_NAME': shell.display_name,
            }
            for name, value in environment_variables.items():
                value = pipes.quote(str(value))
                shell.dispatch_command('export %s=%s\n' % (name, value))
            rank += 1

    for shell in dispatchers.all_instances():
        if shell.enabled:
            shell.dispatch_command('export POLYSH_NR_SHELLS=%d\n' % rank)


add_to_history('$POLYSH_RANK $POLYSH_NAME $POLYSH_DISPLAY_NAME')
add_to_history('$POLYSH_NR_SHELLS')


def complete_set_log(line, text):
    return complete_local_path(text)


def do_set_log(command):
    """
    Usage: :set_log [LOCAL_PATH]
    Duplicate every console I/O into the given local file.
    If LOCAL_PATH is not given, restore the default behaviour of not logging.
    """
    command = command.strip()
    if command:
        try:
            remote_dispatcher.options.log_file = open(command, 'a')
        except IOError as e:
            console_output('%s\n' % str(e))
            command = None
    if not command:
        remote_dispatcher.options.log_file = None
        console_output('Logging disabled\n')


def complete_show_read_buffer(line, text):
    return complete_shells(line, text, lambda i: i.read_buffer or
                           i.read_in_state_not_started)


def do_show_read_buffer(command):
    """
    Usage: :show_read_buffer [SHELLS...]
    Print the data read by remote shells.
    The special characters * ? and [] work as expected.
    """
    for i in selected_shells(command):
        if i.read_in_state_not_started:
            i.print_lines(i.read_in_state_not_started)
            i.read_in_state_not_started = ''


def main():
    """
    Output a help text of each control command suitable for the man page
    Run from the polysh top directory: python -m polysh.control_commands
    """
    try:
        man_page = open('polysh.1', 'r')
    except IOError as e:
        print(e)
        print('Please run "python -m polysh.control_commands" from the' +
              ' polysh top directory')
        sys.exit(1)

    updated_man_page_fd, updated_man_page_path = tempfile.mkstemp()
    updated_man_page = os.fdopen(updated_man_page_fd, 'w')

    # The first line is auto-generated as it contains the version number
    man_page.readline()
    v = '.TH "polysh" "1" "%s" "Guillaume Chazarain" "Remote shells"' % VERSION
    print(v, file=updated_man_page)

    for line in man_page:
        print(line, end=' ', file=updated_man_page)
        if 'BEGIN AUTO-GENERATED CONTROL COMMANDS DOCUMENTATION' in line:
            break

    for name in list_control_commands():
        print('.TP', file=updated_man_page)
        unstripped = get_control_command(name).__doc__.split('\n')
        lines = [l.strip() for l in unstripped]
        usage = lines[1].strip()
        print('\\fB%s\\fR' % usage[7:], file=updated_man_page)
        help_text = ' '.join(lines[2:]).replace('polysh', '\\fIpolysh\\fR')
        print(help_text.strip(), file=updated_man_page)

    for line in man_page:
        if 'END AUTO-GENERATED CONTROL COMMANDS DOCUMENTATION' in line:
            print(line, end=' ', file=updated_man_page)
            break

    for line in man_page:
        print(line, end=' ', file=updated_man_page)

    man_page.close()
    updated_man_page.close()
    shutil.move(updated_man_page_path, 'polysh.1')


if __name__ == '__main__':
    main()
