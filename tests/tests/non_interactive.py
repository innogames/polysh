"""Polysh - Tests - Non-interactive Mode

Copyright (c) 2006 Guillaume Chazarain <guichaz@gmail.com>
Copyright (c) 2018 InnoGames GmbH
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

import unittest
import pexpect
from polysh_tests import launch_polysh


class TestNonInteractive(unittest.TestCase):
    def testCommandNormal(self):
        child = launch_polysh(['--command=echo text', 'localhost'])
        child.expect('\033\[1;36mlocalhost : \033\[1;mtext')
        child.expect(pexpect.EOF)

    def testCommandIntr(self):
        child = launch_polysh(['--command=echo text; cat', 'localhost'])
        child.expect('\033\[1;36mlocalhost : \033\[1;mtext')
        child.sendintr()
        child.expect(pexpect.EOF)

    def testSimpleCommandStdin(self):
        child = launch_polysh(['localhost'], input_data='echo line')
        child.expect('localhost : line')
        child.expect(pexpect.EOF)

    def testMultipleCommandStdin(self):
        commands = """
        echo first
        echo next
        echo last
        """
        child = launch_polysh(['localhost'], input_data=commands)
        child.expect('localhost : first')
        child.expect('localhost : next')
        child.expect('localhost : last')
        child.expect(pexpect.EOF)

    def testInvalidCommandStdin(self):
        child = launch_polysh(
            ['localhost', '--command=date'], input_data='uptime')
        child.expect('--command and reading from stdin are incompatible')
        child.expect(pexpect.EOF)

    def testExitCode(self):
        def CommandCode(command, code):
            child = launch_polysh(
                ['--command=%s' % command] + ['localhost'] * 5)
            child.expect(pexpect.EOF)
            while child.isalive():
                child.wait()
            self.assertEqual(child.exitstatus, code)
        CommandCode('true', 0)
        CommandCode('false', 1)

    def testInvalidCharacters(self):
        child = launch_polysh(
            ["--command=printf '%b' '\xacfoo\u2018bar\n'", 'localhost'])
        child.expect('\033\[1;36mlocalhost : \033\[1;m\xacfoo\u2018bar')
        child.expect(pexpect.EOF)
