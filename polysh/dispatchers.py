"""Polysh - Dispatchers

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
import fcntl
import struct
import sys
import termios
from typing import List
from typing import Tuple

from polysh import remote_dispatcher
from polysh import display_names
from polysh.terminal_size import terminal_size


def _split_port(hostname: str) -> Tuple[str, str]:
    """ Splits a string(hostname, given by the user) into hostname and port,
    returns a tuple """
    s = hostname.split(':', 1)
    if len(s) > 1:
        return s[0], s[1]
    else:
        return s[0], '22'


def all_instances() -> List[remote_dispatcher.RemoteDispatcher]:
    """Iterator over all the remote_dispatcher instances"""
    return sorted([i for i in asyncore.socket_map.values() if
                   isinstance(i, remote_dispatcher.RemoteDispatcher)],
                  key=lambda i: i.display_name or '')


def count_awaited_processes() -> Tuple[int, int]:
    """Return a tuple with the number of awaited processes and the total
    number"""
    awaited = 0
    total = 0
    for i in all_instances():
        if i.enabled:
            total += 1
            if i.state is not remote_dispatcher.STATE_IDLE:
                awaited += 1
    return awaited, total


def all_terminated() -> bool:
    """For each remote shell determine if its terminated"""
    instances_found = False
    for i in all_instances():
        instances_found = True
        if i.state not in (remote_dispatcher.STATE_TERMINATED,
                           remote_dispatcher.STATE_DEAD):
            return False
    return instances_found


def update_terminal_size() -> None:
    """Propagate the terminal size to the remote shells accounting for the
    place taken by the longest name"""
    w, h = terminal_size()
    w = max(w - display_names.max_display_name_length - 2, min(w, 10))
    # python bug http://python.org/sf/1112949 on amd64
    # from ajaxterm.py
    bug = struct.unpack('i', struct.pack('I', termios.TIOCSWINSZ))[0]
    packed_size = struct.pack('HHHH', h, w, 0, 0)
    term_size = w, h
    for i in all_instances():
        if i.enabled and i.term_size != term_size:
            i.term_size = term_size
            fcntl.ioctl(i.fd, bug, packed_size)


def format_info(info_list: List[List[bytes]]) -> List[bytes]:
    """Turn a 2-dimension list of strings into a 1-dimension list of strings
    with correct spacing"""
    max_lengths = []
    if info_list:
        nr_columns = len(info_list[0])
    else:
        nr_columns = 0
    for i in range(nr_columns):
        max_lengths.append(max([len(info[i]) for info in info_list]))

    flattened_info_list = []  # type: List[bytes]
    for info_id in range(len(info_list)):
        info = info_list[info_id]
        for str_id in range(len(info) - 1):
            # Don't justify the last column (i.e. the last printed line)
            # as it can get much longer in some shells than in others
            orig_str = info[str_id]
            indent = max_lengths[str_id] - len(orig_str)
            info[str_id] = orig_str + indent * b' '
        flattened_info_list.append(b' '.join(info) + b'\n')

    return flattened_info_list


def create_remote_dispatchers(hosts: List[str]) -> None:
    last_message = ''
    for i, host in enumerate(hosts):
        if remote_dispatcher.options.interactive:
            last_message = 'Started %d/%d remote processes\r' % (i, len(hosts))
            sys.stdout.write(last_message)
            sys.stdout.flush()
        try:
            hostname, port = _split_port(host)
            remote_dispatcher.RemoteDispatcher(hostname, port)
        except OSError:
            print()
            raise

    if last_message:
        sys.stdout.write(' ' * len(last_message) + '\r')
        sys.stdout.flush()
