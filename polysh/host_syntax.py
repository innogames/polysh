"""Polysh - Hostname Expansion

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

import re
from typing import Iterator
from typing import Tuple

# Currently the only expansion is <START_NUMBER-END_NUMBER>
# <1-10> => 1, 2, 3, 4, 5, 6, 7, 8, 9, 10
# <10-1> => 10, 9, 8, 7, 6, 5, 4, 3, 2, 1
# <01-10> => 01, 02, 03, 04, 05, 06, 07, 08, 09, 10
# <1-4,6-10> => 1, 2, 3, 4, 6, 7, 8, 9, 10
# <1,3-6> => 1, 3, 4, 5, 6
# <1> => 1

syntax_pattern = re.compile('<([0-9,-]+)>')
interval_pattern = re.compile('([0-9]+)(-[0-9]+)?')


def _split_port(hostname: str) -> Tuple[str, str]:
    s = hostname.split(':', 1)
    if len(s) > 1:
        return s[0], s[1]
    else:
        return s[0], '22'


def _iter_numbers(start: str, end: str) -> Iterator[str]:
    int_start = int(start)
    int_end = int(end)
    if int_start < int_end:
        increment = 1
    else:
        increment = -1
    zero_pad = len(start) > 1 and start.startswith('0') or \
        len(end) > 1 and end.startswith('0')
    if zero_pad:
        length = max(len(start), len(end))
    for i in range(int_start, int_end + increment, increment):
        s = str(i)
        if zero_pad:
            s = s.zfill(length)
        yield s


def expand_syntax(string: str) -> Iterator[str]:
    """Iterator over all the strings in the expansion of the argument"""
    match = syntax_pattern.search(string)
    if match:
        prefix = string[:match.start()]
        suffix = string[match.end():]
        intervals = match.group(1).split(',')
        for interval in intervals:
            interval_match = interval_pattern.match(interval)
            if interval_match:
                start = interval_match.group(1)
                end = (interval_match.group(2) or start).strip('-')
                for i in _iter_numbers(start, end):
                    for expanded in expand_syntax(prefix + i + suffix):
                        yield expanded
    else:
        yield string
