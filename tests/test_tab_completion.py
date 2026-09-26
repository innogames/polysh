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

import os
import stat
import tempfile
import unittest

import pexpect

from tests import launch_polysh
from tests.test_custom_prompt import FAKE_SHELL


class TestTabCompletion(unittest.TestCase):
    """A --prompt remote is used here only because it makes the control shell
    reachable without depending on the local login shell."""

    def setUp(self):
        fd, self.shell = tempfile.mkstemp(prefix='polysh_fake_shell.')
        os.write(fd, FAKE_SHELL.encode())
        os.close(fd)
        os.chmod(self.shell, os.stat(self.shell).st_mode | stat.S_IXUSR)

    def tearDown(self):
        os.remove(self.shell)

    def testControlCommandCompletion(self):
        child = launch_polysh(
            [
                f'--ssh={self.shell}',
                '--prompt=racadm>>',
                '--no-color',
                'host1',
                'host2',
            ]
        )
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
