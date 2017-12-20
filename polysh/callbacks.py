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

# Polysh uses specially crafted strings to communicate out of band data with
# remote shells. This includes detecting the shell prompt, and other events to
# detect.
# These strings are built and sent in two parts, the remote shell should send
# back the concatenation of these two strings to trigger the callback. This is
# to insure that the sending of the trigger to the remote shell does not trigger
# the callback.
#
# Example: The trigger FOOBAR could be split into FOO and BAR and sent as
#          echo "FOO""BAR" so that the sent string does not contain FOOBAR.

import random

DIGITS_LETTERS = list(map(str, list(range(10))))                     + \
                 list(map(chr, list(range(ord('a'), ord('z') + 1)))) + \
                 list(map(chr, list(range(ord('A'), ord('Z') + 1))))

def random_string(length):
    def random_char():
        return DIGITS_LETTERS[random.randint(0, len(DIGITS_LETTERS) - 1)]
    return ''.join([random_char() for i in range(length)])

COMMON_PREFIX = 'polysh-%s:' % random_string(5)
NR_GENERATED_TRIGGERS = 0

# {'random_string()': (function, repeat)}
CALLBACKS = {}

def add(name, function, repeat):
    name = name.replace('/', '_')
    global NR_GENERATED_TRIGGERS
    nr = NR_GENERATED_TRIGGERS
    NR_GENERATED_TRIGGERS += 1
    trigger = '%s%s:%s:%d/' % (COMMON_PREFIX, name, random_string(5), nr)
    CALLBACKS[trigger] = (function, repeat)
    trigger1 = trigger[:len(COMMON_PREFIX)/2]
    trigger2 = trigger[len(trigger1):]
    return trigger1, trigger2

def any_in(data):
    return COMMON_PREFIX in data

def process(line):
    start = line.find(COMMON_PREFIX)
    if start < 0:
        return False

    end = line.find('/', start) + 1
    if end <= 0:
        return False

    trigger = line[start:end]
    callback, repeat = CALLBACKS.get(trigger, (None, True))
    if not callback:
        return False

    if not repeat:
        del CALLBACKS[trigger]

    callback(line[end:].strip())
    return True

