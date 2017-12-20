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
# Copyright (c) 2007 Guillaume Chazarain <guichaz@gmail.com>

import unittest
import pexpect
from polysh_tests import launch_polysh

class TestHostSyntax(unittest.TestCase):
    def assertHostSyntax(self, to_expand, expanded):
        child = launch_polysh([to_expand, 'localhost'])
        child.expect('ready')
        child.sendline(':list')
        with_spaces = [e.replace('.', '\\.') + ' ' for e in expanded]
        for i in range(len(expanded)):
            found = child.expect(with_spaces)
            del with_spaces[found]
        child.expect('ready')
        child.sendeof()
        child.expect(pexpect.EOF)

    def testHostSyntax(self):
        self.assertHostSyntax('0.0.0.<0-10>',
                              ['0.0.0.0', '0.0.0.1', '0.0.0.2', '0.0.0.3',
                               '0.0.0.4', '0.0.0.5', '0.0.0.6', '0.0.0.7',
                               '0.0.0.8', '0.0.0.9', '0.0.0.10'])
        self.assertHostSyntax('0.0.0.<00-10>',
                              ['0.0.0.00', '0.0.0.01', '0.0.0.02', '0.0.0.03',
                               '0.0.0.04', '0.0.0.05', '0.0.0.06', '0.0.0.07',
                               '0.0.0.08', '0.0.0.09', '0.0.0.10'])
        self.assertHostSyntax('0.0.0.<1-10>',
                              ['0.0.0.1', '0.0.0.2', '0.0.0.3', '0.0.0.4',
                               '0.0.0.5', '0.0.0.6', '0.0.0.7', '0.0.0.8',
                               '0.0.0.9', '0.0.0.10'])
        self.assertHostSyntax('0.0.0.<10-1>',
                              ['0.0.0.1', '0.0.0.2', '0.0.0.3', '0.0.0.4',
                               '0.0.0.5', '0.0.0.6', '0.0.0.7', '0.0.0.8',
                               '0.0.0.9', '0.0.0.10'])
        self.assertHostSyntax('0.0.0.<01-10>',
                              ['0.0.0.01', '0.0.0.02', '0.0.0.03', '0.0.0.04',
                               '0.0.0.05', '0.0.0.06', '0.0.0.07', '0.0.0.08',
                               '0.0.0.09', '0.0.0.10'])
        self.assertHostSyntax('0.0.<1-4>.<01-03>',
                              ['0.0.1.01', '0.0.1.02', '0.0.1.03', '0.0.2.01',
                               '0.0.2.02', '0.0.2.03', '0.0.3.01', '0.0.3.02',
                               '0.0.3.03', '0.0.4.01', '0.0.4.02', '0.0.4.03'])
        self.assertHostSyntax('0.0.0.<1>', ['0.0.0.1'])
        self.assertHostSyntax('0.0.0.<1,3-5>',
                              ['0.0.0.1', '0.0.0.3', '0.0.0.4', '0.0.0.5'])

