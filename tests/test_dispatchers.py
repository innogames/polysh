"""Polysh - Tests - Dispatchers

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

import fcntl
import os
import struct
import termios
from types import SimpleNamespace

import pytest

from polysh import dispatchers
from polysh.dispatchers import _split_port, format_info


def test_format_info_nothing():
    assert format_info([]) == []


def test_format_info_single_row():
    assert format_info([[b'host', b'enabled', b'idle:', b'']]) == [
        b'host enabled idle: \n'
    ]


def test_format_info_pads_all_but_the_last_column():
    rows = [
        [b'a', b'enabled', b'x'],
        [b'abc', b'disabled', b'a much longer last line'],
    ]
    assert format_info(rows) == [
        b'a   enabled  x\n',
        b'abc disabled a much longer last line\n',
    ]


@pytest.mark.parametrize(('host', 'split'), [
    ('host', ('host', '22')),
    ('host:2222', ('host', '2222')),
    ('[::1]:22', ('[', ':1]:22')),
])
def test_split_port(host, split):
    assert _split_port(host) == split


def test_update_terminal_size_uses_unsigned_request(monkeypatch):
    """TIOCSWINSZ does not fit in a signed int on macOS: passing it
    converted to a negative number makes the ioctl fail with ENOTTY"""
    master, slave = os.openpty()
    remote = SimpleNamespace(enabled=True, term_size=(-1, -1), fd=master)
    monkeypatch.setattr(dispatchers, 'all_instances', lambda: [remote])
    monkeypatch.setattr(dispatchers, 'terminal_size', lambda: (80, 24))
    monkeypatch.setattr(dispatchers.display_names, 'max_display_name_length', 0)
    try:
        dispatchers.update_terminal_size()
        rows, cols, _, _ = struct.unpack(
            'HHHH', fcntl.ioctl(slave, termios.TIOCGWINSZ, b'\0' * 8)
        )
    finally:
        os.close(master)
        os.close(slave)
    assert (cols, rows) == (78, 24)
