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
import os

from gsh_tests import launch_gsh

class TestCommandLine(unittest.TestCase):
    def testGoodHostsFilename(self):
        tmp_name = '/tmp/gsh_tests.%d' % (os.getpid())
        tmp = open(tmp_name, 'w', 0600)
        print >> tmp, 'localhost # Comment'
        print >> tmp, '127.0.0.1'
        print >> tmp, '# Ignore me'
        print >> tmp, 'localhost.localdomain'
        tmp.close()
        child = launch_gsh(['--hosts-file=%s' % (tmp_name)])
        child.expect('ready \(3\)> ')
        child.sendeof()
        child.expect(pexpect.EOF)
        os.remove(tmp_name)

    def testBadHostsFilename(self):
        child = launch_gsh(['--hosts-file=do not exist/at all'])
        child.expect('error')
        child.expect(pexpect.EOF)

    def testNoHosts(self):
        child = launch_gsh([])
        child.expect('error: no hosts given')
        child.expect(pexpect.EOF)
        child = launch_gsh(['--hosts-file=/dev/null'])
        child.expect('error: no hosts given')
        child.expect(pexpect.EOF)

TESTS = (TestCommandLine,)
