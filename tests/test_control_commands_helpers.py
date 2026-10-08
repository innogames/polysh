"""Polysh - Tests - Control Command Helpers

Unit tests for the shell selection behind the control commands, run
against stubs instead of remote shells.

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

import readline

import pytest

from polysh import control_commands, remote_dispatcher
from polysh.control_commands_helpers import (
    complete_control_command,
    complete_shells,
    expand_local_path,
    get_control_command,
    handle_control_command,
    list_control_commands,
    selected_shells,
    toggle_shells,
)


class FakeShell:
    def __init__(
        self,
        display_name,
        enabled=True,
        state=remote_dispatcher.STATE_IDLE,
        last_printed_line=b'',
    ):
        self.display_name = display_name
        self.enabled = enabled
        self.state = state
        self.last_printed_line = last_printed_line
        self.toggles = []

    def set_enabled(self, enabled):
        self.toggles.append(enabled)
        self.enabled = enabled

    def __repr__(self):
        return f'FakeShell({self.display_name!r})'


@pytest.fixture
def shells(monkeypatch):
    """The shells all_instances() returns, a list to fill"""
    shells = []
    monkeypatch.setattr('polysh.dispatchers.all_instances', lambda: shells)
    return shells


@pytest.fixture
def console(monkeypatch):
    """What the helpers print, as a list of bytes"""
    output = []
    monkeypatch.setattr(
        'polysh.control_commands_helpers.console_output', output.append
    )
    return output


def names(iterable):
    return [shell.display_name for shell in iterable]


@pytest.mark.parametrize('command', ['', '*'])
def test_selected_shells_all(shells, command):
    shells += [FakeShell('a'), FakeShell('b')]
    assert names(selected_shells(command)) == ['a', 'b']


def test_selected_shells_glob(shells, console):
    shells += [FakeShell('web1'), FakeShell('web2'), FakeShell('db1')]
    assert names(selected_shells('web*')) == ['web1', 'web2']
    assert console == []


def test_selected_shells_expands_host_syntax(shells):
    shells += [FakeShell('web1'), FakeShell('web2'), FakeShell('web3')]
    assert names(selected_shells('web<1-2>')) == ['web1', 'web2']


def test_selected_shells_yields_each_shell_once(shells):
    shells += [FakeShell('web1'), FakeShell('web2')]
    assert names(selected_shells('web* web1')) == ['web1', 'web2']


def test_selected_shells_reports_unmatched_pattern(shells, console):
    shells += [FakeShell('web1')]
    assert names(selected_shells('db* web1')) == ['web1']
    assert console == [b'db* not found\n']


def test_selected_shells_matches_last_printed_line(shells):
    shells += [
        FakeShell('a', last_printed_line=b'all fine'),
        FakeShell('b', last_printed_line=b'segfault'),
    ]
    assert names(selected_shells('*segfault*')) == ['b']


def test_toggle_shells_skips_dead_shells(shells):
    alive = FakeShell('alive')
    dead = FakeShell('dead', state=remote_dispatcher.STATE_DEAD)
    shells += [alive, dead]
    toggle_shells('*', False)
    assert alive.toggles == [False]
    assert dead.toggles == []


def test_toggle_shells_inverts_the_others_when_nothing_would_change(shells):
    """:disable a with a already disabled means: only a stays disabled"""
    a = FakeShell('a', enabled=False)
    b = FakeShell('b', enabled=False)
    c = FakeShell('c', enabled=True)
    shells += [a, b, c]
    toggle_shells('a', False)
    assert (a.enabled, b.enabled, c.enabled) == (False, True, True)


def test_toggle_shells_plain(shells):
    a = FakeShell('a', enabled=True)
    b = FakeShell('b', enabled=True)
    shells += [a, b]
    toggle_shells('a', False)
    assert (a.enabled, b.enabled) == (False, True)


def test_complete_shells(shells):
    shells += [FakeShell('web1'), FakeShell('web2'), FakeShell('db1')]
    assert complete_shells(':list we', 'we') == ['web1 ', 'web2 ']
    # Names already on the line are not offered again
    assert complete_shells(':list web1 we', 'we') == ['web2 ']
    assert complete_shells(':list ', '', lambda s: s.display_name[0] == 'd') == [
        'db1 '
    ]


def test_expand_local_path(monkeypatch, tmp_path):
    monkeypatch.setenv('HOME', str(tmp_path))
    monkeypatch.setenv('POLYSH_TEST_DIR', '/some/where')
    assert expand_local_path('') == str(tmp_path)
    assert expand_local_path('~/logs') == str(tmp_path / 'logs')
    assert expand_local_path('$POLYSH_TEST_DIR/x') == '/some/where/x'


def test_control_command_lookup():
    commands = list_control_commands()
    assert 'quit' in commands
    assert 'enable' in commands
    assert all(not c.startswith('do_') for c in commands)
    assert get_control_command('quit') is control_commands.do_quit
    with pytest.raises(AttributeError):
        get_control_command('unknown')


def test_complete_control_command_name(monkeypatch):
    monkeypatch.setattr(readline, 'get_begidx', lambda: 0)
    assert complete_control_command(':dis', ':dis') == [':disable ']
    assert complete_control_command(':nothing', ':nothing') == []


def test_complete_control_command_arguments(monkeypatch, shells):
    shells += [FakeShell('web1')]
    monkeypatch.setattr(readline, 'get_begidx', lambda: 6)
    assert complete_control_command(':list w', 'w') == ['web1 ']
    # A command without completion offers nothing
    assert complete_control_command(':quit w', 'w') == []


def test_handle_control_command(console, monkeypatch):
    calls = []
    monkeypatch.setattr(control_commands, 'do_rename', calls.append)
    handle_control_command('rename new name')
    assert calls == ['new name']
    handle_control_command('')
    assert console == []


def test_handle_control_command_unknown(console):
    handle_control_command('frobnicate now')
    assert console == [b'Unknown control command: frobnicate\n']


def test_handle_control_command_reports_a_failing_command(console, monkeypatch):
    """A failing control command must not take the session down with it"""

    def failing(parameters):
        raise ValueError('boom')

    monkeypatch.setattr(control_commands, 'do_rename', failing)
    handle_control_command('rename x')
    assert console == [b'Error in control command rename: ValueError: boom\n']
