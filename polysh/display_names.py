"""Polysh - Displaying Names

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

from typing import Dict, List, Optional
from collections import defaultdict
# The prefix is the key, the value is a list of booleans. A boolean at an
# index is True if that index is currently in use.
PREFIXES = defaultdict(lambda: [])  # type: Dict[str, List[bool]]

# dict with key:len(display_name) value:nr of enabled shells with a
# display_name of such a length
NR_ENABLED_DISPLAY_NAMES_BY_LENGTH = dict()  # type: Dict[int, int]

# Used for terminal size and layout
max_display_name_length = 0


def acquire_prefix_index(prefix: str) -> int:
    # Search and reuse removed host suffix
    for idx, item in enumerate(PREFIXES[prefix]):
        if not item:
            PREFIXES[prefix][idx] = True
            return idx

    # Add new suffix if no old suffix can be reused
    PREFIXES[prefix].append(True)
    return len(PREFIXES[prefix]) - 1


def release_prefix_index(prev_display_name: str) -> None:
    split = prev_display_name.split('#', 1)
    prefix = split[0]
    if len(split) == 1:
        suffix = 0
    else:
        suffix = int(split[1])

    # We are not deleting the host with the highest suffix. Therefore we need
    # to mark the current suffix index as unused.
    if suffix < len(PREFIXES[prefix]) - 1:
        PREFIXES[prefix][suffix] = False
        return None

    # We are deleting the host with the highest suffix. Therefore we need to
    # delete it.
    del PREFIXES[prefix][suffix]

    # Remove holes previously left.
    for idx, in_use in reversed(list(enumerate(PREFIXES[prefix]))):
        if in_use:
            return None
        del PREFIXES[prefix][idx]

    # If we arrived here, we just deleted the last item with a specific
    # prefix. Therefore we need to delete the whole prefix now.
    del PREFIXES[prefix]


def make_unique_name(prefix: str) -> str:
    suffix = acquire_prefix_index(prefix)
    if suffix:
        return '{}#{}'.format(prefix, suffix)

    return prefix


def update_max_display_name_length() -> None:
    from polysh.dispatchers import update_terminal_size
    new_max = max(NR_ENABLED_DISPLAY_NAMES_BY_LENGTH.keys(), default=0)
    global max_display_name_length
    if new_max != max_display_name_length:
        max_display_name_length = new_max
        update_terminal_size()


def change(
    prev_display_name: Optional[str],
    new_prefix: Optional[str]
) -> Optional[str]:
    if new_prefix and '#' in new_prefix:
        raise Exception('Names cannot contain #')

    if prev_display_name is not None:
        if new_prefix is not None:
            set_enabled(prev_display_name, False)
        release_prefix_index(prev_display_name)
        if new_prefix is None:
            return None

    name = make_unique_name(new_prefix)
    set_enabled(name, True)

    return name


def set_enabled(display_name: str, enabled: bool) -> None:
    length = len(display_name)
    if enabled:
        if length in NR_ENABLED_DISPLAY_NAMES_BY_LENGTH:
            NR_ENABLED_DISPLAY_NAMES_BY_LENGTH[length] += 1
        else:
            NR_ENABLED_DISPLAY_NAMES_BY_LENGTH[length] = 1
    else:
        NR_ENABLED_DISPLAY_NAMES_BY_LENGTH[length] -= 1
        if not NR_ENABLED_DISPLAY_NAMES_BY_LENGTH[length]:
            del NR_ENABLED_DISPLAY_NAMES_BY_LENGTH[length]

    update_max_display_name_length()
