"""Polysh - Tests - Custom Prompt

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

from tests.fake_shells import FAKE_SHELL, FAKE_SHELL_NO_EXIT


def test_interactive(polysh, fake_shell):
    child = polysh([
        f'--ssh={fake_shell(FAKE_SHELL)}',
        '--prompt=racadm>>',
        '--no-color',
        'host1',
        'host2',
    ])
    child.expect(r'ready \(2\)> ')
    child.sendline('getsysinfo')
    child.expect(r'host1 : out\[getsysinfo\]')
    child.expect(r'host2 : out\[getsysinfo\]')
    child.expect(r'ready \(2\)> ')
    child.sendline('exit')
    child.expect(pexpect.EOF)


def test_non_interactive(polysh, fake_shell):
    child = polysh([
        f'--ssh={fake_shell(FAKE_SHELL)}',
        '--prompt=racadm>>',
        '--no-color',
        '--command=getsysinfo',
        'host1',
    ])
    child.expect(pexpect.EOF)
    output = child.before
    assert 'host1 : out[getsysinfo]' in output
    assert 'host1 : bye' in output
    # The prompt itself is never reported as remote output
    assert 'racadm>>' not in output


def test_remote_ignoring_exit(polysh, fake_shell):
    child = polysh([
        f'--ssh={fake_shell(FAKE_SHELL_NO_EXIT)}',
        '--prompt=racadm>>',
        '--no-color',
        '--command=getsysinfo',
        'host1',
    ])
    child.expect(pexpect.EOF)
    output = child.before
    assert 'host1 : out[getsysinfo]' in output
    assert 'racadm>>' not in output


def test_bad_regexp(polysh):
    child = polysh(['--prompt=racadm(>>', 'host1'])
    child.expect('error: invalid --prompt regex')
    child.expect(pexpect.EOF)
