"""Polysh - Tests - Display Names

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

import pexpect
import pytest

from polysh import display_names


@pytest.mark.slow
def test_hole(polysh):
    """Names freed by :purge are reused by :add, filling the holes in the
    numbering first"""
    child = polysh(['--ssh=sh;:'] + ['a'] * 100)
    child.expect(r'ready \(100\)> ')
    child.sendline(':disable *1*')
    child.expect(r'ready \(81\)> ')
    child.sendline('exit')
    child.expect(r'ready \(0\)> ')
    child.sendline(':enable')
    child.expect(r'ready \(19\)> ')
    child.sendline(':purge')
    child.expect(r'ready \(19\)> ')
    for i in range(20, 101):
        child.sendline(':add a')
        child.expect(rf'ready \({i}\)> ')
    child.sendline(':quit')
    child.expect(pexpect.EOF)


@pytest.fixture
def names(monkeypatch):
    """The display_names module with its state reset, and without the
    terminal size update that changing a name triggers"""
    monkeypatch.setattr('polysh.dispatchers.update_terminal_size', lambda: None)
    display_names.PREFIXES.clear()
    display_names.NR_ENABLED_DISPLAY_NAMES_BY_LENGTH.clear()
    display_names.max_display_name_length = 0
    yield display_names
    display_names.PREFIXES.clear()
    display_names.NR_ENABLED_DISPLAY_NAMES_BY_LENGTH.clear()
    display_names.max_display_name_length = 0


def test_unique_names_are_numbered(names):
    assert names.make_unique_name('a') == 'a'
    assert names.make_unique_name('a') == 'a#1'
    assert names.make_unique_name('a') == 'a#2'
    assert names.make_unique_name('b') == 'b'


def test_released_number_is_reused(names):
    for _ in range(3):
        names.make_unique_name('a')
    names.release_prefix_index('a#1')
    assert names.make_unique_name('a') == 'a#1'
    assert names.make_unique_name('a') == 'a#3'


def test_releasing_the_highest_number_trims_the_holes(names):
    for _ in range(3):
        names.make_unique_name('a')
    names.release_prefix_index('a#1')
    names.release_prefix_index('a#2')
    assert names.PREFIXES['a'] == [True]
    assert names.make_unique_name('a') == 'a#1'


def test_releasing_the_last_name_forgets_the_prefix(names):
    names.make_unique_name('a')
    names.release_prefix_index('a')
    assert 'a' not in names.PREFIXES


def test_change_tracks_the_longest_enabled_name(names):
    assert names.change(None, 'a') == 'a'
    assert names.max_display_name_length == 1
    assert names.change(None, 'long') == 'long'
    assert names.max_display_name_length == 4
    assert names.change('long', 'ab') == 'ab'
    assert names.max_display_name_length == 2
    assert names.NR_ENABLED_DISPLAY_NAMES_BY_LENGTH == {1: 1, 2: 1}
    # Giving a name up, as RemoteDispatcher.close() does once disconnect()
    # has disabled the shell
    names.set_enabled('ab', False)
    names.set_enabled('a', False)
    assert names.NR_ENABLED_DISPLAY_NAMES_BY_LENGTH == {}
    assert names.max_display_name_length == 0
    assert names.change('ab', None) is None
    assert names.change('a', None) is None
    assert dict(names.PREFIXES) == {}


def test_disabled_names_do_not_count(names):
    names.change(None, 'a')
    names.change(None, 'long')
    names.set_enabled('long', False)
    assert names.max_display_name_length == 1
    names.set_enabled('long', True)
    assert names.max_display_name_length == 4


def test_names_cannot_contain_a_hash(names):
    with pytest.raises(Exception, match='cannot contain #'):
        names.change(None, 'a#1')
