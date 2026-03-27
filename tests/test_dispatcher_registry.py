"""Polysh - Tests - Dispatcher Registry

Unit tests for the selectors-based dispatcher registry.

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

import os
import selectors
import unittest

from polysh import dispatcher_registry


class FakeDispatcher:
    """Minimal dispatcher stub for testing."""

    def __init__(self, fd):
        self.fd = fd
        self._readable = True
        self._writable = False

    def readable(self):
        return self._readable

    def writable(self):
        return self._writable


class TestDispatcherRegistry(unittest.TestCase):
    def setUp(self):
        """Reset module-level global state and track fds for cleanup."""
        self._fds = []
        dispatcher_registry._dispatchers.clear()
        dispatcher_registry._current_events.clear()
        dispatcher_registry._selector.close()
        dispatcher_registry._selector = selectors.DefaultSelector()

    def tearDown(self):
        """Close all pipe fds opened during the test."""
        # Unregister any remaining dispatchers first to avoid selector complaints
        for fd in list(dispatcher_registry._dispatchers):
            dispatcher_registry.unregister(fd)
        dispatcher_registry._selector.close()
        dispatcher_registry._selector = selectors.DefaultSelector()
        for fd in self._fds:
            try:
                os.close(fd)
            except OSError:
                pass

    def _make_pipe(self):
        """Create a pipe and track both fds for cleanup."""
        r, w = os.pipe()
        self._fds.extend([r, w])
        return r, w

    def test_register_and_get_dispatcher(self):
        r, w = self._make_pipe()
        d = FakeDispatcher(r)
        dispatcher_registry.register(r, d)

        self.assertIs(dispatcher_registry.get_dispatcher(r), d)
        # Selector should have it registered with EVENT_READ
        key = dispatcher_registry.get_selector().get_key(r)
        self.assertEqual(key.events, selectors.EVENT_READ)
        self.assertIs(key.data, d)

    def test_register_sets_current_events(self):
        r, w = self._make_pipe()
        d = FakeDispatcher(r)
        dispatcher_registry.register(r, d)

        self.assertEqual(
            dispatcher_registry._current_events[r], selectors.EVENT_READ
        )

    def test_unregister(self):
        r, w = self._make_pipe()
        d = FakeDispatcher(r)
        dispatcher_registry.register(r, d)
        dispatcher_registry.unregister(r)

        self.assertIsNone(dispatcher_registry.get_dispatcher(r))
        self.assertNotIn(r, dispatcher_registry._current_events)
        with self.assertRaises(KeyError):
            dispatcher_registry.get_selector().get_key(r)

    def test_unregister_unknown_fd_is_noop(self):
        # Should not raise
        dispatcher_registry.unregister(99999)

    def test_unregister_already_unregistered(self):
        r, w = self._make_pipe()
        d = FakeDispatcher(r)
        dispatcher_registry.register(r, d)
        dispatcher_registry.unregister(r)
        # Second unregister should be a safe noop
        dispatcher_registry.unregister(r)

    def test_modify_events_caching(self):
        """modify_events should skip syscall when events unchanged."""
        r, w = self._make_pipe()
        d = FakeDispatcher(r)
        dispatcher_registry.register(r, d)

        # Initial state is EVENT_READ. Calling modify with same events is a noop.
        dispatcher_registry.modify_events(r, selectors.EVENT_READ)
        key = dispatcher_registry.get_selector().get_key(r)
        self.assertEqual(key.events, selectors.EVENT_READ)

    def test_modify_events_read_to_readwrite(self):
        r, w = self._make_pipe()
        d = FakeDispatcher(r)
        dispatcher_registry.register(r, d)

        both = selectors.EVENT_READ | selectors.EVENT_WRITE
        dispatcher_registry.modify_events(r, both)

        key = dispatcher_registry.get_selector().get_key(r)
        self.assertEqual(key.events, both)
        self.assertEqual(dispatcher_registry._current_events[r], both)

    def test_modify_events_to_zero_unregisters_from_selector(self):
        r, w = self._make_pipe()
        d = FakeDispatcher(r)
        dispatcher_registry.register(r, d)

        dispatcher_registry.modify_events(r, 0)

        # Should be unregistered from selector but still in _dispatchers
        with self.assertRaises(KeyError):
            dispatcher_registry.get_selector().get_key(r)
        self.assertIs(dispatcher_registry.get_dispatcher(r), d)
        self.assertEqual(dispatcher_registry._current_events[r], 0)

    def test_modify_events_zero_to_read_reregisters(self):
        r, w = self._make_pipe()
        d = FakeDispatcher(r)
        dispatcher_registry.register(r, d)

        # Unregister from selector
        dispatcher_registry.modify_events(r, 0)
        # Re-register
        dispatcher_registry.modify_events(r, selectors.EVENT_READ)

        key = dispatcher_registry.get_selector().get_key(r)
        self.assertEqual(key.events, selectors.EVENT_READ)

    def test_modify_events_unknown_fd_is_noop(self):
        # Should not raise
        dispatcher_registry.modify_events(99999, selectors.EVENT_READ)

    def test_all_dispatchers_returns_list_copy(self):
        r, w = self._make_pipe()
        d = FakeDispatcher(r)
        dispatcher_registry.register(r, d)

        result = dispatcher_registry.all_dispatchers()
        self.assertIsInstance(result, list)
        self.assertEqual(result, [d])
        # Mutating the returned list should not affect the registry
        result.clear()
        self.assertEqual(dispatcher_registry.all_dispatchers(), [d])

    def test_iter_dispatchers(self):
        r, w = self._make_pipe()
        d = FakeDispatcher(r)
        dispatcher_registry.register(r, d)

        result = list(dispatcher_registry.iter_dispatchers())
        self.assertEqual(result, [d])

    def test_multiple_dispatchers(self):
        r1, w1 = self._make_pipe()
        r2, w2 = self._make_pipe()
        d1 = FakeDispatcher(r1)
        d2 = FakeDispatcher(r2)
        dispatcher_registry.register(r1, d1)
        dispatcher_registry.register(r2, d2)

        self.assertEqual(len(dispatcher_registry.all_dispatchers()), 2)
        self.assertIs(dispatcher_registry.get_dispatcher(r1), d1)
        self.assertIs(dispatcher_registry.get_dispatcher(r2), d2)

        dispatcher_registry.unregister(r1)
        self.assertEqual(len(dispatcher_registry.all_dispatchers()), 1)
        self.assertIsNone(dispatcher_registry.get_dispatcher(r1))
        self.assertIs(dispatcher_registry.get_dispatcher(r2), d2)

    def test_get_dispatcher_returns_none_for_unknown(self):
        self.assertIsNone(dispatcher_registry.get_dispatcher(99999))


if __name__ == '__main__':
    unittest.main()
