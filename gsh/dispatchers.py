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
# Copyright (c) 2006, 2007, 2008 Guillaume Chazarain <guichaz@gmail.com>

import asyncore
import fcntl
import struct
import termios

from gsh import remote_dispatcher
from gsh.terminal_size import terminal_size

def all_instances():
    """Iterator over all the remote_dispatcher instances"""
    for i in asyncore.socket_map.itervalues():
        if isinstance(i, remote_dispatcher.remote_dispatcher):
            yield i

def make_unique_name(name):
    """Each shell must have a unique display name, so identical hostnames are
    suffixed by #NUMBER"""
    display_names = set([i.display_name for i in all_instances()])
    candidate_name = name
    i = 0
    while candidate_name in display_names:
        i += 1
        candidate_name = '%s#%d' % (name, i)
    return candidate_name

def count_awaited_processes():
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

def all_terminated():
    """For each remote shell we determine if its terminated by checking if
    it is in the right state or if it requested termination but will never
    receive the acknowledgement"""
    instances_found = False
    for i in all_instances():
        instances_found = True
        if i.active and i.state is not remote_dispatcher.STATE_TERMINATED:
            if i.enabled or not i.termination:
                return False
    return instances_found

max_display_name_length = 0
def update_max_display_name_length(change):
    """The max_display_name_length serves to compute the length of the
    whitespace used to align the output of the remote shells. A positive change
    argument indicates that a remote shells with such a name length was enabled
    while a negative change argument indicates a disabled remote shell"""
    global max_display_name_length

    if change < 0:
        if -change < max_display_name_length:
            # The disabled shell didn't have the longest name
            return
        new_max = 0
        for i in all_instances():
            if i.enabled:
                l = len(i.display_name)
                if l >= -change:
                    # The disabled shell was not alone with the longest name
                    return
                new_max = max(l, new_max)
    else:
        new_max = max(change, max_display_name_length)

    if new_max != max_display_name_length:
        max_display_name_length = new_max
        update_terminal_size()

def update_terminal_size():
    """Propagate the terminal size to the remote shells accounting for the
    place taken by the longest name"""
    w, h = terminal_size()
    w = max(w - max_display_name_length - 2, min(w, 10))
    # python bug http://python.org/sf/1112949 on amd64
    # from ajaxterm.py
    bug = struct.unpack('i', struct.pack('I', termios.TIOCSWINSZ))[0]
    packed_size = struct.pack('HHHH', h, w, 0, 0)
    term_size = w, h
    for i in all_instances():
        if i.enabled and i.term_size != term_size:
            i.term_size = term_size
            fcntl.ioctl(i.fd, bug, packed_size)

def format_info(info_list):
    """Turn a 2-dimension list of strings into a 1-dimension list of strings
    with correct spacing"""
    info_list.sort(key=lambda i:int(i[1][3:]))
    max_lengths = []
    if info_list:
        nr_columns = len(info_list[0])
    else:
        nr_columns = 0
    for i in xrange(nr_columns):
        max_lengths.append(max([len(str(info[i])) for info in info_list]))
    for info_id in xrange(len(info_list)):
        info = info_list[info_id]
        for str_id in xrange(len(info)):
            orig_str = str(info[str_id])
            indent = max_lengths[str_id] - len(orig_str)
            info[str_id] = orig_str + indent * ' '
        info_list[info_id] = ' '.join(info)


