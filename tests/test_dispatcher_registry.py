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

import pytest

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


@pytest.fixture(autouse=True)
def registry():
    """Reset the module-level state of the registry around each test"""
    dispatcher_registry._dispatchers.clear()
    dispatcher_registry._current_events.clear()
    dispatcher_registry._selector.close()
    dispatcher_registry._selector = selectors.DefaultSelector()
    yield dispatcher_registry
    # Unregister any remaining dispatchers first to avoid selector complaints
    for fd in list(dispatcher_registry._dispatchers):
        dispatcher_registry.unregister(fd)
    dispatcher_registry._selector.close()
    dispatcher_registry._selector = selectors.DefaultSelector()


@pytest.fixture
def pipe():
    """Factory for pipes, both ends closed at teardown"""
    fds = []

    def make():
        r, w = os.pipe()
        fds.extend([r, w])
        return r, w

    yield make
    for fd in fds:
        try:
            os.close(fd)
        except OSError:
            pass


def test_register_and_get_dispatcher(pipe):
    r, w = pipe()
    d = FakeDispatcher(r)
    dispatcher_registry.register(r, d)

    assert dispatcher_registry.get_dispatcher(r) is d
    # Selector should have it registered with EVENT_READ
    key = dispatcher_registry.get_selector().get_key(r)
    assert key.events == selectors.EVENT_READ
    assert key.data is d


def test_register_sets_current_events(pipe):
    r, w = pipe()
    d = FakeDispatcher(r)
    dispatcher_registry.register(r, d)

    assert dispatcher_registry._current_events[r] == selectors.EVENT_READ


def test_unregister(pipe):
    r, w = pipe()
    d = FakeDispatcher(r)
    dispatcher_registry.register(r, d)
    dispatcher_registry.unregister(r)

    assert dispatcher_registry.get_dispatcher(r) is None
    assert r not in dispatcher_registry._current_events
    with pytest.raises(KeyError):
        dispatcher_registry.get_selector().get_key(r)


def test_unregister_unknown_fd_is_noop():
    dispatcher_registry.unregister(99999)


def test_unregister_already_unregistered(pipe):
    r, w = pipe()
    d = FakeDispatcher(r)
    dispatcher_registry.register(r, d)
    dispatcher_registry.unregister(r)
    # Second unregister should be a safe noop
    dispatcher_registry.unregister(r)


def test_modify_events_caching(pipe):
    """modify_events should skip syscall when events unchanged."""
    r, w = pipe()
    d = FakeDispatcher(r)
    dispatcher_registry.register(r, d)

    # Initial state is EVENT_READ. Calling modify with same events is a noop.
    dispatcher_registry.modify_events(r, selectors.EVENT_READ)
    key = dispatcher_registry.get_selector().get_key(r)
    assert key.events == selectors.EVENT_READ


def test_modify_events_read_to_readwrite(pipe):
    r, w = pipe()
    d = FakeDispatcher(r)
    dispatcher_registry.register(r, d)

    both = selectors.EVENT_READ | selectors.EVENT_WRITE
    dispatcher_registry.modify_events(r, both)

    key = dispatcher_registry.get_selector().get_key(r)
    assert key.events == both
    assert dispatcher_registry._current_events[r] == both


def test_modify_events_to_zero_unregisters_from_selector(pipe):
    r, w = pipe()
    d = FakeDispatcher(r)
    dispatcher_registry.register(r, d)

    dispatcher_registry.modify_events(r, 0)

    # Should be unregistered from selector but still in _dispatchers
    with pytest.raises(KeyError):
        dispatcher_registry.get_selector().get_key(r)
    assert dispatcher_registry.get_dispatcher(r) is d
    assert dispatcher_registry._current_events[r] == 0


def test_modify_events_zero_to_read_reregisters(pipe):
    r, w = pipe()
    d = FakeDispatcher(r)
    dispatcher_registry.register(r, d)

    # Unregister from selector
    dispatcher_registry.modify_events(r, 0)
    # Re-register
    dispatcher_registry.modify_events(r, selectors.EVENT_READ)

    key = dispatcher_registry.get_selector().get_key(r)
    assert key.events == selectors.EVENT_READ


def test_modify_events_unknown_fd_is_noop():
    dispatcher_registry.modify_events(99999, selectors.EVENT_READ)


def test_all_dispatchers_returns_list_copy(pipe):
    r, w = pipe()
    d = FakeDispatcher(r)
    dispatcher_registry.register(r, d)

    result = dispatcher_registry.all_dispatchers()
    assert isinstance(result, list)
    assert result == [d]
    # Mutating the returned list should not affect the registry
    result.clear()
    assert dispatcher_registry.all_dispatchers() == [d]


def test_iter_dispatchers(pipe):
    r, w = pipe()
    d = FakeDispatcher(r)
    dispatcher_registry.register(r, d)

    assert list(dispatcher_registry.iter_dispatchers()) == [d]


def test_multiple_dispatchers(pipe):
    r1, w1 = pipe()
    r2, w2 = pipe()
    d1 = FakeDispatcher(r1)
    d2 = FakeDispatcher(r2)
    dispatcher_registry.register(r1, d1)
    dispatcher_registry.register(r2, d2)

    assert len(dispatcher_registry.all_dispatchers()) == 2
    assert dispatcher_registry.get_dispatcher(r1) is d1
    assert dispatcher_registry.get_dispatcher(r2) is d2

    dispatcher_registry.unregister(r1)
    assert len(dispatcher_registry.all_dispatchers()) == 1
    assert dispatcher_registry.get_dispatcher(r1) is None
    assert dispatcher_registry.get_dispatcher(r2) is d2


def test_get_dispatcher_returns_none_for_unknown():
    assert dispatcher_registry.get_dispatcher(99999) is None
