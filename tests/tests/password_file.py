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
# Copyright (c) 2009 Guillaume Chazarain <guichaz@gmail.com>

import os
import unittest
import pexpect
from gsh_tests import launch_gsh

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
            os.unlink('/tmp/gsh_test.log')
        except OSError:
            # File not found
            pass
        passwd = '--password-file=' + password_file
        child = launch_gsh([SSH_ARG, passwd, '--debug',
                            '--log-file=/tmp/gsh_test.log', '1', '2'])
        return child

    def endTestPassword(self):
        self.failIf('sikr3t' in file('/tmp/gsh_test.log').read())
        os.unlink('/tmp/gsh_test.log')

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
        print >> file('/tmp/gsh_test.pwd', 'w'), 'noidea'
        child = self.startTestPassword('/tmp/gsh_test.pwd')
        child.expect(pexpect.EOF)
        while child.isalive():
            child.wait()
        os.unlink('/tmp/gsh_test.pwd')
        self.assertEqual(child.exitstatus, 13)
        self.endTestPassword()

    def testGoodPasswordFile(self):
        print >> file('/tmp/gsh_test.pwd', 'w'), 'sikr3t'
        child = self.startTestPassword('/tmp/gsh_test.pwd')
        child.expect('ready \(2\)> ')
        os.unlink('/tmp/gsh_test.pwd')
        child.sendline(':quit')
        child.expect(pexpect.EOF)
        while child.isalive():
            child.wait()
        self.assertEqual(child.exitstatus, 0)
        self.endTestPassword()
