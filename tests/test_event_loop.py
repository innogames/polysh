"""Polysh - Tests - Event Loop

Unit tests for the selectors-based event loop.

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
from polysh.event_loop import loop_iteration


class FakeDispatcher:
    """Dispatcher stub that records which handlers were called."""

    def __init__(self, fd, readable=True, writable=False):
        self.fd = fd
        self._readable = readable
        self._writable = writable
        self.read_called = 0
        self.write_called = 0
        self.close_called = 0

    def readable(self):
        return self._readable

    def writable(self):
        return self._writable

    def handle_read(self):
        self.read_called += 1

    def handle_write(self):
        self.write_called += 1

    def handle_close(self):
        self.close_called += 1


class FailingReadDispatcher(FakeDispatcher):
    """Dispatcher whose handle_read raises an exception."""

    def handle_read(self):
        self.read_called += 1
        raise RuntimeError('read failed')


class FailingWriteDispatcher(FakeDispatcher):
    """Dispatcher whose handle_write raises an exception."""

    def handle_write(self):
        self.write_called += 1
        raise RuntimeError('write failed')


class SelfUnregisteringDispatcher(FakeDispatcher):
    """Dispatcher that unregisters itself during handle_read."""

    def handle_read(self):
        self.read_called += 1
        dispatcher_registry.unregister(self.fd)


class TestEventLoop(unittest.TestCase):
    def setUp(self):
        self._fds = []
        dispatcher_registry._dispatchers.clear()
        dispatcher_registry._current_events.clear()
        dispatcher_registry._selector.close()
        dispatcher_registry._selector = selectors.DefaultSelector()

    def tearDown(self):
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
        r, w = os.pipe()
        self._fds.extend([r, w])
        return r, w

    def test_readable_dispatcher_gets_handle_read(self):
        r, w = self._make_pipe()
        # Write something so the read end becomes ready
        os.write(w, b'hello')

        d = FakeDispatcher(r, readable=True, writable=False)
        dispatcher_registry.register(r, d)

        loop_iteration(timeout=0.1)
        self.assertGreaterEqual(d.read_called, 1)
        self.assertEqual(d.write_called, 0)

    def test_writable_dispatcher_gets_handle_write(self):
        r, w = self._make_pipe()
        # Write end of a pipe is immediately writable
        d = FakeDispatcher(w, readable=False, writable=True)
        dispatcher_registry.register(w, d)

        loop_iteration(timeout=0.1)
        self.assertEqual(d.read_called, 0)
        self.assertGreaterEqual(d.write_called, 1)

    def test_both_readable_and_writable(self):
        r, w = self._make_pipe()
        os.write(w, b'data')

        # Use the read end for reading, write end for writing
        dr = FakeDispatcher(r, readable=True, writable=False)
        dw = FakeDispatcher(w, readable=False, writable=True)
        dispatcher_registry.register(r, dr)
        dispatcher_registry.register(w, dw)

        loop_iteration(timeout=0.1)
        self.assertGreaterEqual(dr.read_called, 1)
        self.assertGreaterEqual(dw.write_called, 1)

    def test_not_readable_not_writable_skipped(self):
        r, w = self._make_pipe()
        os.write(w, b'data')

        d = FakeDispatcher(r, readable=False, writable=False)
        dispatcher_registry.register(r, d)

        loop_iteration(timeout=0.1)
        self.assertEqual(d.read_called, 0)
        self.assertEqual(d.write_called, 0)

    def test_no_dispatchers_does_not_raise(self):
        # Empty registry, should just return after timeout
        loop_iteration(timeout=0.01)

    def test_handle_read_exception_triggers_handle_close(self):
        r, w = self._make_pipe()
        os.write(w, b'data')

        d = FailingReadDispatcher(r, readable=True, writable=False)
        dispatcher_registry.register(r, d)

        loop_iteration(timeout=0.1)
        self.assertGreaterEqual(d.read_called, 1)
        self.assertGreaterEqual(d.close_called, 1)

    def test_handle_write_exception_triggers_handle_close(self):
        r, w = self._make_pipe()

        d = FailingWriteDispatcher(w, readable=False, writable=True)
        dispatcher_registry.register(w, d)

        loop_iteration(timeout=0.1)
        self.assertGreaterEqual(d.write_called, 1)
        self.assertGreaterEqual(d.close_called, 1)

    def test_dispatcher_removed_during_handle_read_skips_handle_write(self):
        """If handle_read unregisters the dispatcher, handle_write must not run."""
        r, w = self._make_pipe()
        os.write(w, b'data')

        # Dispatcher that claims both readable and writable, but unregisters
        # itself on read — handle_write must be skipped
        d = SelfUnregisteringDispatcher(r, readable=True, writable=True)
        dispatcher_registry.register(r, d)

        loop_iteration(timeout=0.1)
        self.assertGreaterEqual(d.read_called, 1)
        self.assertEqual(d.write_called, 0)

    def test_events_updated_between_iterations(self):
        """Dispatcher state changes should be reflected in the next iteration."""
        r, w = self._make_pipe()
        os.write(w, b'data')

        d = FakeDispatcher(r, readable=True, writable=False)
        dispatcher_registry.register(r, d)

        loop_iteration(timeout=0.1)
        self.assertGreaterEqual(d.read_called, 1)

        # Now make it not readable
        read_count = d.read_called
        d._readable = False
        loop_iteration(timeout=0.05)
        self.assertEqual(d.read_called, read_count)

    def test_multiple_dispatchers_independent(self):
        """Multiple dispatchers should be handled independently."""
        r1, w1 = self._make_pipe()
        r2, w2 = self._make_pipe()
        os.write(w1, b'data1')
        # r2 has no data, so not ready for read

        d1 = FakeDispatcher(r1, readable=True, writable=False)
        d2 = FakeDispatcher(r2, readable=True, writable=False)
        dispatcher_registry.register(r1, d1)
        dispatcher_registry.register(r2, d2)

        loop_iteration(timeout=0.1)
        self.assertGreaterEqual(d1.read_called, 1)
        self.assertEqual(d2.read_called, 0)


if __name__ == '__main__':
    unittest.main()
