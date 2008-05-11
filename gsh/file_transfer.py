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

import base64
import random

from gsh import callbacks
from gsh import pity
from gsh.console import console_output

def base64version(module):
    path = module.__file__
    if path.endswith('.pyc'):
        # Read from the .py source file
        path = path[:-1]
    python_lines = []
    for line in file(path):
        hash_pos = line.find(chr(35))
        if hash_pos < 0:
            line = line[:hash_pos]
        line = line.rstrip()
        if line:
            python_lines.append(line)
    python_source = '\n'.join(python_lines)
    encoded = base64.encodestring(python_source).rstrip('\n').replace('\n', ',')
    return encoded

CMD_PREFIX = 'python -c "`echo "' + base64version(pity) + '"|' + \
                         'tr , \\\\\\n|' + \
                         'openssl base64 -d`" '

CMD_SEND = CMD_PREFIX + 'send "%s" "%s" "%s"\n'
CMD_FORWARD = CMD_PREFIX + 'forward "%s" "%s"\n'
CMD_RECEIVE = CMD_PREFIX + 'receive "%s" "%s"\n'

def file_transfer_cb(dispatcher, host_port):
    previous_shell = get_previous_shell(dispatcher)
    previous_shell.dispatch_write(host_port + '\n')

def get_infos():
    """Returns (first, last)"""
    from gsh import dispatchers
    first = None
    last = None
    for i in dispatchers.all_instances():
        if i.enabled:
            if not first:
                first = i
            last = i
    return first, last

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
        cb = lambda host_port, i=i: file_transfer_cb(i, host_port)
        transfer1, transfer2 = callbacks.add('file transfer', cb, False)
        if i == shell:
            i.dispatch_command(CMD_SEND % (path, transfer1, transfer2))
        elif i != receiver:
            i.dispatch_command(CMD_FORWARD % (transfer1, transfer2))
        else:
            i.dispatch_command(CMD_RECEIVE % (transfer1, transfer2))
        i.change_state(remote_dispatcher.STATE_RUNNING)

