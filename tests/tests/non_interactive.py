# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Library General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 59 Temple Place - Suite 330, Boston, MA 02111-1307, USA.
#
# See the COPYING file for license information.
#
# Copyright (c) 2007, 2008 Guillaume Chazarain <guichaz@gmail.com>

import os
import unittest
import pexpect
from gsh_tests import launch_gsh

class TestNonInteractive(unittest.TestCase):
    def testCommandNormal(self):
        child = launch_gsh(['--command=echo text', 'localhost'])
        child.expect('\033\[1;36mlocalhost : \033\[1;mtext')
        child.expect(pexpect.EOF)

    def testCommandIntr(self):
        child = launch_gsh(['--command=echo text; cat', 'localhost'])
        child.expect('\033\[1;36mlocalhost : \033\[1;mtext')
        child.sendintr()
        child.expect(pexpect.EOF)

    def testSimpleCommandStdin(self):
        child = launch_gsh(['localhost'], input_data='echo line')
        child.expect('localhost : line')
        child.expect(pexpect.EOF)

    def testMultipleCommandStdin(self):
        commands = """
        echo first
        echo next
        echo last
        """
        child = launch_gsh(['localhost'], input_data=commands)
        child.expect('localhost : first')
        child.expect('localhost : next')
        child.expect('localhost : last')
        child.expect(pexpect.EOF)

    def testInvalidCommandStdin(self):
        child = launch_gsh(['localhost', '--command=date'], input_data='uptime')
        child.expect('--command and reading from stdin are incompatible')
        child.expect(pexpect.EOF)

    def testExitCode(self):
        def CommandCode(command, code):
            child = launch_gsh(['--command=%s' % command] + ['localhost'] * 5)
            child.expect(pexpect.EOF)
            while child.isalive():
                child.wait()
            self.assertEqual(child.exitstatus, code)
        CommandCode('true', 0)
        CommandCode('false', 1)

