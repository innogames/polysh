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
# Copyright (c) 2007, 2008 Guillaume Chazarain <guichaz@yahoo.fr>

import unittest
import pexpect
from gsh_tests import launch_gsh

class TestControlCommands(unittest.TestCase):
    def testControl(self):
        child = launch_gsh(['localhost'])
        child.expect('ready \(1\)> ')
        child.sendline('cat')
        child.expect('waiting \(1/1\)> ')
        child.sendline(':send_ctrl z')
        child.expect('ready \(1\)> ')
        child.sendline('fg')
        child.expect('waiting \(1/1\)> ')
        child.sendline(':send_ctrl d')
        child.expect('ready \(1\)> ')
        child.sendline('sleep 1h')
        child.expect('waiting \(1/1\)> ')
        child.sendline(':disabl\tlocal* not_found\t')
        child.expect('not_found not found\r\n')
        child.expect('ready \(0\)> ')
        child.sendline(':help')
        child.sendline(':enable local\t')
        child.sendline(':list')
        child.expect('1 active shells, 0 dead shells, total: 1')
        child.sendline(':send_ctrl c')
        child.expect('ready \(1\)> ')
        child.sendline(':quit')
        child.expect(pexpect.EOF)

    def testReconnect(self):
        child = launch_gsh(['localhost', 'localhost'])
        child.expect('ready \(2\)> ')
        child.sendline(':disable localhost')
        child.sendline('exit')
        child.expect('Error talking to localhost#1\r\n')
        child.expect('ready \(0\)>')
        child.sendline(':reconnect l\t')
        child.sendline(':enable')
        child.expect('ready \(2\)> ')
        child.sendeof()
        child.expect(pexpect.EOF)

    def testListManipulation(self):
        child = launch_gsh(['localhost'])
        child.expect('ready \(1\)> ')
        child.sendline(':add localhost')
        child.expect('ready \(2\)> ')
        child.sendline(':rename $(echo newname)')
        child.expect('ready \(2\)> ')
        child.sendline('date')
        child.expect('newname')
        child.expect('newname')
        child.sendline(':disable newname')
        child.sendline(':purge')
        child.sendline(':enable *')
        child.expect('ready \(1\)> ')
        child.sendline(':rename')
        child.expect('ready \(1\)> ')
        child.sendline('date')
        child.expect('localhost:')
        child.expect('ready \(1\)> ')
        child.sendeof()
        child.expect(pexpect.EOF)

TESTS = (TestControlCommands,)
