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

import unittest
import pexpect
from gsh_tests import launch_gsh

class TestHostSyntax(unittest.TestCase):
    def assertHostSyntax(self, to_expand, expanded):
        child = launch_gsh([to_expand, 'localhost'])
        child.expect('ready')
        child.sendline(':list')
        with_spaces = [e + ' ' for e in expanded]
        for i in xrange(len(expanded)):
            found = child.expect(with_spaces)
            del with_spaces[found]
        child.expect('total: %d' % (len(expanded) + 1))
        child.expect('ready')
        child.sendeof()
        child.expect(pexpect.EOF)

    def testHostSyntax(self):
        self.assertHostSyntax('host<1-10>',
                              ['host1', 'host2', 'host3', 'host4', 'host5',
                               'host6', 'host7', 'host8', 'host9', 'host10'])
        self.assertHostSyntax('host<10-1>',
                              ['host1', 'host2', 'host3', 'host4', 'host5',
                               'host6', 'host7', 'host8', 'host9', 'host10'])
        self.assertHostSyntax('host<01-10>',
                              ['host01', 'host02', 'host03', 'host04',
                               'host05', 'host06', 'host07', 'host08',
                               'host09', 'host10'])
        self.assertHostSyntax('host<1-4>-<01-03>',
                              ['host1-01', 'host1-02', 'host1-03', 'host2-01',
                               'host2-02', 'host2-03', 'host3-01', 'host3-02',
                               'host3-03', 'host4-01', 'host4-02', 'host4-03'])

TESTS = (TestHostSyntax,)
