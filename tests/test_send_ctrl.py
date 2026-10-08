"""Polysh - Tests - Sending Control Keys

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

from tests.fake_shells import REPORTING_SHELL

BACKSLASH = chr(92)


@pytest.fixture
def child(polysh, fake_shell):
    """polysh at its prompt, talking to a shell that names the control
    bytes it receives"""
    child = polysh([
        f'--ssh={fake_shell(REPORTING_SHELL)}',
        '--prompt=racadm>>',
        '--no-color',
        '-l',
        'host1',
    ])
    child.expect(r'ready \(1\)> ')
    return child


def test_send_ctrl_backslash(child):
    child.sendline(':send_ctrl ' + BACKSLASH)
    child.expect(r'got\[CTRL-BACKSLASH\]')
    child.expect(r'ready \(1\)> ')
    child.sendline(':quit')
    child.expect(pexpect.EOF)


def test_send_ctrl_letter(child):
    child.sendline(':send_ctrl c')
    child.expect(r'got\[CTRL-C\]')
    child.expect(r'ready \(1\)> ')
    child.sendline(':send_ctrl z')
    child.expect(r'got\[CTRL-Z\]')
    child.expect(r'ready \(1\)> ')
    child.sendline(':quit')
    child.expect(pexpect.EOF)


def test_unsendable_argument_is_reported(child):
    """This used to raise out of the dispatcher, which closed the stdin
    notification socket and killed polysh on the next prompt."""
    child.sendline(':send_ctrl %')
    child.expect(r'Expected a letter or one of')
    child.expect(r'ready \(1\)> ')
    # Still alive and usable
    child.sendline('getractime')
    child.expect(r'out\[getractime\]')
    child.expect(r'ready \(1\)> ')
    child.sendline(':quit')
    child.expect(pexpect.EOF)


def test_local_ctrl_backslash_is_forwarded(child):
    child.send('\x1c')
    child.expect(r'got\[CTRL-BACKSLASH\]')
    child.expect(r'ready \(1\)> ')
    child.sendline(':quit')
    child.expect(pexpect.EOF)
