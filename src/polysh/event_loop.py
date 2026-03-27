"""Polysh - Event Loop

Provides the main loop iteration using selectors, replacing asyncore.loop().

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

import errno
import selectors
from typing import Optional

from polysh import dispatcher_registry


def loop_iteration(timeout: Optional[float] = None) -> None:
    """Perform a single iteration of the event loop.

    This replaces asyncore.loop(count=1, timeout=timeout, use_poll=True).

    Updates selector registrations based on each dispatcher's readable()/writable()
    state, then performs select and dispatches events to handlers.
    """
    selector = dispatcher_registry.get_selector()

    # Update event registrations based on current readable/writable state.
    # Iterate the dict values directly — this loop doesn't mutate _dispatchers.
    for dispatcher in dispatcher_registry.iter_dispatchers():
        events = 0
        if dispatcher.readable():
            events |= selectors.EVENT_READ
        if dispatcher.writable():
            events |= selectors.EVENT_WRITE
        dispatcher_registry.modify_events(dispatcher.fd, events)

    # Perform select
    try:
        ready = selector.select(timeout)
    except OSError as e:
        if e.errno == errno.EINTR:
            # Interrupted by signal handler, just return
            return
        raise

    # Dispatch events
    for key, events in ready:
        dispatcher = key.data

        # Check if dispatcher is still valid
        if dispatcher_registry.get_dispatcher(key.fd) is None:
            continue

        if events & selectors.EVENT_READ:
            try:
                dispatcher.handle_read()
            except Exception:
                dispatcher.handle_close()

        # Re-check dispatcher is still valid after handle_read
        if dispatcher_registry.get_dispatcher(key.fd) is None:
            continue

        if events & selectors.EVENT_WRITE:
            try:
                dispatcher.handle_write()
            except Exception:
                dispatcher.handle_close()
