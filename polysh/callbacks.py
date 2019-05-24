"""Polysh - Callbacks

Polysh uses specially crafted strings to communicate out of band data with
remote shells. This includes detecting the shell prompt, and other events to
detect.

These strings are built and sent in two parts, the remote shell should send
back the concatenation of these two strings to trigger the callback. This is
to insure that the sending of the trigger to the remote shell does not
trigger the callback.

Example: The trigger FOOBAR could be split into FOO and BAR and sent as
         echo "FOO""BAR" so that the sent string does not contain FOOBAR.

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

import random
from typing import Callable
from typing import Tuple

DIGITS_LETTERS = list(map(str, list(range(10)))) + \
    list(map(chr, list(range(ord('a'), ord('z') + 1)))) + \
    list(map(chr, list(range(ord('A'), ord('Z') + 1))))


def random_string(length: int) -> str:
    def random_char() -> str:
        return DIGITS_LETTERS[random.randint(0, len(DIGITS_LETTERS) - 1)]
    return ''.join([random_char() for i in range(length)])


COMMON_PREFIX = 'polysh-{}:'.format(random_string(5)).encode()
NR_GENERATED_TRIGGERS = 0

# {'random_string()': (function, repeat)}
CALLBACKS = {}


def add(name: bytes, function: Callable, repeat: bool) -> Tuple[bytes, bytes]:
    name = name.replace(b'/', b'_')
    global NR_GENERATED_TRIGGERS
    nr = NR_GENERATED_TRIGGERS
    NR_GENERATED_TRIGGERS += 1
    trigger = (COMMON_PREFIX + name + b':' + random_string(5).encode() + b':' +
               str(nr).encode() + b'/')
    CALLBACKS[trigger] = (function, repeat)
    trigger1 = trigger[:int(len(COMMON_PREFIX) / 2)]
    trigger2 = trigger[len(trigger1):]
    return trigger1, trigger2


def any_in(data: bytes) -> bool:
    return COMMON_PREFIX in data


def process(line: bytes) -> bool:
    start = line.find(COMMON_PREFIX)
    if start < 0:
        return False

    end = line.find(b'/', start) + 1
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
