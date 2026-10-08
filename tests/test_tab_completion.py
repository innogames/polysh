"""Polysh - Tests - Tab Completion

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

from tests.fake_shells import FAKE_SHELL


def test_control_command_completion(polysh, fake_shell):
    """A --prompt remote is used here only because it makes the control
    shell reachable without depending on the local login shell."""
    child = polysh([
        f'--ssh={fake_shell(FAKE_SHELL)}',
        '--prompt=racadm>>',
        '--no-color',
        'host1',
        'host2',
    ])
    child.expect(r'ready \(2\)> ')
    child.send(':dis\t')
    # Terminal redraws may sit between the typed prefix and the completed
    # remainder, so only look for what completion added
    child.expect('able')
    # And the completed command is a real one
    child.sendline('host2')
    child.expect(r'ready \(1\)> ')
    child.sendline(':quit')
    child.expect(pexpect.EOF)
