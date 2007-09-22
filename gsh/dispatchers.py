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
import fcntl
import struct
import termios
import time

from gsh import remote_dispatcher
from gsh.terminal_size import terminal_size

def all_instances():
    """Iterator over all the remote_dispatcher instances"""
    for i in asyncore.socket_map.itervalues():
        if isinstance(i, remote_dispatcher.remote_dispatcher):
            yield i

def make_unique_name(name):
    display_names = set([i.display_name for i in all_instances()])
    candidate_name = name
    i = 0
    while candidate_name in display_names:
        i += 1
        candidate_name = '%s#%d' % (name, i)
    return candidate_name

def count_completed_processes():
    """Return a tuple with the number of ready processes and the total number"""
    completed_processes = 0
    total = 0
    for i in all_instances():
        if i.enabled:
            total += 1
            if i.state is remote_dispatcher.STATE_IDLE:
                completed_processes += 1
    return completed_processes, total

def handle_unfinished_lines():
    """Typically we print only lines with a '\n', but if some buffers keep an
    unfinished line for some time we'll add an artificial '\n'"""
    for r in all_instances():
        if r.read_buffer and r.read_buffer[0] != chr(27):
            break
    else:
        # No unfinished lines
        return

    begin = time.time()
    asyncore.loop(count=1, timeout=0.2, use_poll=True)
    duration = time.time() - begin
    if duration >= 0.15:
        for r in all_instances():
            r.print_unfinished_line()

def dispatch_termination_to_all():
    """Start the termination procedure in all remote shells"""
    for r in all_instances():
        r.dispatch_termination()

def all_terminated():
    """For each remote shell we determine if its terminated by checking if
    it is in the right state or if it requested termination but will never
    receive the acknowledgement"""
    for i in all_instances():
        if i.state is not remote_dispatcher.STATE_TERMINATED:
            if i.enabled or not i.termination:
                return False
    return True

def update_terminal_size():
    """Propagate the terminal size to the remote shells accounting for the
    place taken by the longest name"""
    w, h = terminal_size()
    lengths = [len(i.display_name) for i in all_instances() if i.enabled]
    if not lengths:
        return
    max_name_len = max(lengths)
    for i in all_instances():
        padding_len = max_name_len - len(i.display_name)
        new_prefix = i.display_name + padding_len * ' ' + ': '
        if len(new_prefix) < len(i.prefix) and not i.options.interactive:
            # In non-interactive mode, remote processes leave as soon
            # as they are terminated, but we don't want to break the
            # indentation if all the remaining processes have short names.
            return
        i.prefix = new_prefix
    w = max(w - max_name_len - 2, min(w, 10))
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


