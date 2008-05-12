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

def random_string(length):
    def random_char():
        return DIGITS_LETTERS[random.randint(0, len(DIGITS_LETTERS) - 1)]
    return ''.join(map(lambda i: random_char(), xrange(length)))

COMMON_PREFIX = 'gsh-%s:' % random_string(5)
NR_GENERATED_TRIGGERS = 0

# {'random_string()': (function, continuous)}
CALLBACKS = {}

def add(name, function, continous):
    name = name.replace('/', '_')
    global NR_GENERATED_TRIGGERS
    nr = NR_GENERATED_TRIGGERS
    NR_GENERATED_TRIGGERS += 1
    trigger = '%s:%s:%s:%d/' % (COMMON_PREFIX, name, random_string(5), nr)
    CALLBACKS[trigger] = (function, continous)
    trigger1 = trigger[:len(COMMON_PREFIX)/2]
    trigger2 = trigger[len(trigger1):]
    return trigger1, trigger2

def contains(data):
    return COMMON_PREFIX in data

def process(line):
    start = line.find(COMMON_PREFIX)
    if start < 0:
        return False

    end = line.find('/', start) + 1
    if end <= 0:
        return False

    trigger = line[start:end]
    callback, continous = CALLBACKS.get(trigger, (None, True))
    if not callback:
        return False

    if not continous:
        del CALLBACKS[trigger]

    callback(line[end:].strip())
    return True

