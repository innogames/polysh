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
# Copyright (c) 2007, 2008 Guillaume Chazarain <guichaz@gmail.com>

import random

import pity

from gsh.console import console_output

CMD_PREFIX = 'python -c "`echo "' + pity.ENCODED + '"|' + \
                         'tr , \\\\\\n|' + \
                         'openssl base64 -d`" '

CMD_SEND = CMD_PREFIX + '%d send "%s" "%s" "%s"\n'
CMD_FORWARD = CMD_PREFIX + '%d forward "%s" "%s"\n'
CMD_RECEIVE = CMD_PREFIX + '%d receive "%s" "%s"\n'

def received_cookie(dispatcher, line):
    host_port = line[len(dispatcher.file_transfer_cookie) + 1:]
    dispatcher.file_transfer_cookie = None
    previous_shell = get_previous_shell(dispatcher)
    previous_shell.dispatch_write(host_port + '\n')

def get_infos():
    """Returns (nr_peers, first, last)"""
    from gsh import dispatchers
    nr_peers = 0
    first = None
    last = None
    for i in dispatchers.all_instances():
        if i.enabled:
            nr_peers += 1
            if not first:
                first = i
            last = i
    return nr_peers, first, last

def get_previous_shell(shell):
    from gsh import dispatchers
    shells = [i for i in dispatchers.all_instances() if i.enabled]
    current_pos = shells.index(shell)
    while True:
        current_pos = (current_pos - 1) % len(shells)
        prev_shell = shells[current_pos]
        if prev_shell.enabled:
            return prev_shell

def replicate(shell, path):
    from gsh import dispatchers
    from gsh import remote_dispatcher
    nr_peers = len([i for i in dispatchers.all_instances() if i.enabled])
    if nr_peers <= 1:
        console_output('No other remote shell to replicate files to\n')
        return
    receiver = get_previous_shell(shell)
    for i in dispatchers.all_instances():
        if not i.enabled:
            continue
        cookie1 = '[gsh file transfer ' + str(random.random())[2:]
        cookie2 = str(random.random())[2:] + ']'
        i.file_transfer_cookie = cookie1 + cookie2
        if i == shell:
            i.dispatch_command(CMD_SEND % (nr_peers, path, cookie1, cookie2))
        elif i != receiver:
            i.dispatch_command(CMD_FORWARD % (nr_peers, cookie1, cookie2))
        else:
            i.dispatch_command(CMD_RECEIVE % (nr_peers, cookie1, cookie2))
        i.change_state(remote_dispatcher.STATE_RUNNING)

