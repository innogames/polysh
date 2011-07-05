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
# Copyright (c) 2008 Guillaume Chazarain <guichaz@gmail.com>

from polysh.rb_tree import RBTree

# {'prefix': <display_name_prefix object>}
PREFIXES = {}

# Red/black tree with key:len(display_name) value:nr of enabled shells with a
# display_name of such a length
NR_ENABLED_DISPLAY_NAMES_BY_LENGTH = RBTree()

# Cache the right most element in the NR_ENABLED_DISPLAY_NAMES_BY_LENGTH tree
max_display_name_length = 0

class display_name_prefix(object):
    def __init__(self):
        self.next_suffix = 0
        self.holes = RBTree()

    def new_suffix(self):
        if len(self.holes) == 0:
            suffix = self.next_suffix
            self.next_suffix += 1
        else:
            first_node = self.holes.firstNode()
            suffix = first_node.key
            self.holes.deleteNode(first_node)
        return suffix

    def putback_suffix(self, suffix):
        if suffix + 1 != self.next_suffix:
            self.holes.insertNode(suffix, suffix)
            return

        self.next_suffix = suffix
        while True:
            prev_suffix = self.next_suffix - 1
            prev_suffix_node = self.holes.findNode(prev_suffix)
            if not prev_suffix_node:
                return
            self.holes.deleteNode(prev_suffix_node)
            self.next_suffix = prev_suffix

    def empty(self):
        return self.next_suffix == 0

def make_unique_name(prefix):
    prefix_obj = PREFIXES.get(prefix, None)
    if prefix_obj is None:
        prefix_obj = display_name_prefix()
        PREFIXES[prefix] = prefix_obj

    suffix = prefix_obj.new_suffix()
    if suffix:
        name = '%s#%d' % (prefix, suffix)
    else:
        name = prefix

    return name

def update_max_display_name_length():
    from polysh import dispatchers
    if len(NR_ENABLED_DISPLAY_NAMES_BY_LENGTH) == 0:
        new_max = 0
    else:
        new_max = NR_ENABLED_DISPLAY_NAMES_BY_LENGTH.lastNode().key
    global max_display_name_length
    if new_max != max_display_name_length:
        max_display_name_length = new_max
        dispatchers.update_terminal_size()

def change(prev_display_name, new_prefix):
    if new_prefix and '#' in new_prefix:
        raise Exception('Names cannot contain #')

    if prev_display_name is not None:
        if new_prefix is not None:
            set_enabled(prev_display_name, False)
        split = prev_display_name.split('#')
        prev_prefix = split[0]
        if len(split) == 1:
            prev_suffix = 0
        else:
            prev_suffix = int(split[1])
        prefix_obj = PREFIXES[prev_prefix]
        prefix_obj.putback_suffix(prev_suffix)
        if prefix_obj.empty():
            del PREFIXES[prev_prefix]
        if new_prefix is None:
            return

    name = make_unique_name(new_prefix)
    set_enabled(name, True)

    return name

def set_enabled(display_name, enabled):
    length = len(display_name)
    node = NR_ENABLED_DISPLAY_NAMES_BY_LENGTH.findNode(length)
    if enabled:
        if node:
            node.value += 1
        else:
            NR_ENABLED_DISPLAY_NAMES_BY_LENGTH.insertNode(length, 1)
    else:
        node.value -= 1
        if not node.value:
            NR_ENABLED_DISPLAY_NAMES_BY_LENGTH.deleteNode(node)

    update_max_display_name_length()

