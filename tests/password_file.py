"""Polysh - Tests - Password File Support

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

import os
import unittest
import pexpect
from polysh_tests import launch_polysh

SSH_ARG = """--ssh=bash -c '
read -p password: -s PASSWD;
if [ "$PASSWD" = sikr3t ]; then
    bash;
else
    exit 13;
fi; #
'
""".strip()


class TestPasswordFile(unittest.TestCase):
    def startTestPassword(self, password_file):
        try:
            os.unlink('/tmp/polysh_test.log')
        except OSError:
            # File not found
            pass
        passwd = '--password-file=' + password_file
        child = launch_polysh([SSH_ARG, passwd, '--debug',
                               '--log-file=/tmp/polysh_test.log', '1', '2'])
        return child

    def endTestPassword(self):
        self.assertFalse('sikr3t' in open('/tmp/polysh_test.log').read())
        os.unlink('/tmp/polysh_test.log')

    def testGoodPassword(self):
        child = self.startTestPassword('-')
        child.expect('Password:')
        child.sendline('sikr3t')
        child.expect('ready \(2\)> ')
        child.sendline(':quit')
        child.expect(pexpect.EOF)
        self.endTestPassword()

    def testBadPassword(self):
        child = self.startTestPassword('-')
        child.expect('Password:')
        child.sendline('dontknow')
        child.expect(pexpect.EOF)
        while child.isalive():
            child.wait()
        self.assertEqual(child.exitstatus, 13)
        self.endTestPassword()

    def testBadPasswordFile(self):
        print('noidea', file=open('/tmp/polysh_test.pwd', 'w'))
        child = self.startTestPassword('/tmp/polysh_test.pwd')
        child.expect(pexpect.EOF)
        while child.isalive():
            child.wait()
        os.unlink('/tmp/polysh_test.pwd')
        self.assertEqual(child.exitstatus, 13)
        self.endTestPassword()

    def testGoodPasswordFile(self):
        print('sikr3t', file=open('/tmp/polysh_test.pwd', 'w'))
        child = self.startTestPassword('/tmp/polysh_test.pwd')
        child.expect('ready \(2\)> ')
        os.unlink('/tmp/polysh_test.pwd')
        child.sendline(':quit')
        child.expect(pexpect.EOF)
        while child.isalive():
            child.wait()
        self.assertEqual(child.exitstatus, 0)
        self.endTestPassword()
