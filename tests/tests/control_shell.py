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
# Copyright (c) 2007 Guillaume Chazarain <guichaz@yahoo.fr>

import unittest
import pexpect
from gsh_tests import launch_gsh

class TestControlShell(unittest.TestCase):
    def testControl(self):
        child = launch_gsh('--quick-sh localhost')
        child.expect('ready \(1\)> ')
        child.sendline('cat')
        child.expect('waiting \[0/1\]> ')
        child.sendintr()
        child.expect('\[ctrl\]> ')
        child.sendline('send_eof')
        child.sendeof()
        child.expect('ready \(1\)> ')
        child.sendline('sleep 1h')
        child.expect('waiting \[0/1\]> ')
        child.sendintr()
        child.expect('\[ctrl\]> ')
        child.sendline('disabl\tlocal* not_found')
        child.expect('not_found not found\r\n')
        child.sendeof()
        child.expect('ready \(0\)> ')
        child.sendintr()
        child.expect('\[ctrl\]> ')
        child.sendintr()
        child.expect('\[ctrl\]> ')
        child.sendline('help')
        child.sendline('enable local\t')
        child.sendline('list')
        child.expect('1 active shells, 0 dead shells, total: 1')
        child.sendline('send_sigint')
        child.sendline('continue')
        child.expect('ready \(1\)> ')
        child.sendintr()
        child.expect('\[ctrl\]> ')
        child.sendline('quit')
        child.expect(pexpect.EOF)

TESTS = (TestControlShell,)
