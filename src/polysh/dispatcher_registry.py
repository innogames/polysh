"""Polysh - Dispatcher Registry

Manages the global selector and dispatcher tracking, replacing asyncore's socket_map.

Copyright (c) 2006 Guillaume Chazarain <guichaz@gmail.com>
Copyright (c) 2024 InnoGames GmbH
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

import selectors
from typing import Dict, Any, List

# Global selector instance
_selector = selectors.DefaultSelector()

# Mapping from file descriptor to dispatcher instance
_dispatchers: Dict[int, Any] = {}

# Track last-registered events per fd to avoid redundant epoll_ctl syscalls
_current_events: Dict[int, int] = {}


def register(fd: int, dispatcher: Any) -> None:
    """Register a dispatcher with the selector.

    Initially registers with EVENT_READ - events are updated dynamically
    based on readable()/writable() before each select().
    """
    _dispatchers[fd] = dispatcher
    # Register with EVENT_READ initially; loop_iteration will update as needed
    _selector.register(fd, selectors.EVENT_READ, dispatcher)
    _current_events[fd] = selectors.EVENT_READ


def unregister(fd: int) -> None:
    """Unregister a dispatcher from the selector."""
    if fd in _dispatchers:
        del _dispatchers[fd]
        _current_events.pop(fd, None)
        try:
            _selector.unregister(fd)
        except (KeyError, ValueError):
            # Already unregistered or invalid fd
            pass


def modify_events(fd: int, events: int) -> None:
    """Modify the events a dispatcher is interested in.

    Skips the syscall if events haven't changed since last call.

    If events is 0, the fd is temporarily unregistered from the selector
    but kept in _dispatchers. It will be re-registered when events become non-zero.
    """
    if fd not in _dispatchers:
        return

    # Skip if events haven't changed — avoids unnecessary epoll_ctl syscall
    if _current_events.get(fd, 0) == events:
        return

    old_events = _current_events.get(fd, 0)

    if old_events == 0:
        # Not currently registered in selector, need to register
        if events != 0:
            _selector.register(fd, events, _dispatchers[fd])
    elif events == 0:
        # No events - unregister temporarily
        _selector.unregister(fd)
    else:
        # Modify existing registration
        _selector.modify(fd, events, _dispatchers[fd])

    _current_events[fd] = events


def all_dispatchers() -> List[Any]:
    """Return a snapshot list of all registered dispatchers.

    Use iter_dispatchers() when mutation during iteration is not a concern.
    """
    return list(_dispatchers.values())


def iter_dispatchers():
    """Iterate dispatcher values directly, avoiding a list copy.

    Only safe when the caller does not add/remove dispatchers during iteration.
    """
    return _dispatchers.values()


def get_selector() -> selectors.BaseSelector:
    """Return the global selector instance."""
    return _selector


def get_dispatcher(fd: int) -> Any:
    """Return the dispatcher for a given file descriptor, or None."""
    return _dispatchers.get(fd)
