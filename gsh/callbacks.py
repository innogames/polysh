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

import random

DIGITS_LETTERS = map(str, range(10))                     + \
                 map(chr, range(ord('a'), ord('z') + 1)) + \
                 map(chr, range(ord('A'), ord('Z') + 1))

RANDOM_LENGTH = 20

def random_string():
    def random_char():
        return DIGITS_LETTERS[random.randint(0, len(DIGITS_LETTERS) - 1)]
    return ''.join(map(lambda i: random_char(), xrange(RANDOM_LENGTH)))

GSH_COMMON_PREFIX = 'gsh-' + random_string() + ','

# {'random_string()': (function, continuous)}
GSH_CALLBACKS = {}

def add(name, function, continous):
    clean_name = name.replace(':', '_').replace('.', '_')
    trigger1 = clean_name + ':' + random_string() + '/'
    trigger2 = random_string() + '.'
    trigger = trigger1 + trigger2
    GSH_CALLBACKS[trigger] = (function, continous)
    return GSH_COMMON_PREFIX + trigger1, trigger2

def contains(data):
    return GSH_COMMON_PREFIX in data

def process(line):
    start = line.find(GSH_COMMON_PREFIX)
    if start < 0:
        return False

    trigger_start = start + len(GSH_COMMON_PREFIX)
    trigger_end = line.find('.', trigger_start) + 1
    if trigger_end <= 0:
        return False

    trigger = line[trigger_start:trigger_end]
    callback, continous = GSH_CALLBACKS.get(trigger, (None, True))
    if not callback:
        return False

    if not continous:
        del GSH_CALLBACKS[trigger]

    callback(line[trigger_end:])
    return True

