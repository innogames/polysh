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
# Copyright (c) 2008 Guillaume Chazarain <guichaz@gmail.com>

import tempfile
import unittest
import pexpect
import subprocess
from gsh_tests import launch_gsh

def shell_output(command):
    p = subprocess.Popen([command], shell=True, stdout=subprocess.PIPE)
    return p.communicate()[0].strip()

class TestFileTransfer(unittest.TestCase):
    def testReplicate(self):
        tmp_dir = tempfile.mkdtemp()
        local = tmp_dir + '/local'
        child = launch_gsh(['localhost'] * 5)
        child.expect('ready \(5\)> ')
        child.sendline("cd %s" % tmp_dir)
        child.expect('ready \(5\)> ')
        child.sendline('!mkdir %s' % local)
        child.expect('ready \(5\)> ')
        child.sendline('!yes "$(dmesg)" | head -c 20m > %s/file' % local)
        child.expect('ready \(5\)> ')
        child.sendline('!cd %s && sha1sum file > SHA1SUM' % local)
        child.expect('ready \(5\)> ')
        child.sendline(':export_rank')
        child.expect('ready \(5\)> ')
        child.sendline('mkdir $GSH_RANK')
        child.expect('ready \(5\)> ')
        child.sendline('cd $GSH_RANK')
        child.expect('ready \(5\)> ')
        child.sendline(':replicate l\t:%s/file' % local)
        child.expect(': Done transferring 20981760 bytes')
        child.expect('ready \(5\)> ')
        child.sendline('sha1sum file > SHA1SUM')
        child.expect('ready \(5\)> ')
        cat = 'cat %s/*/SHA1SUM' % tmp_dir
        wc_output = shell_output('%s | wc | tr -s " "' % cat)
        self.assertEqual(wc_output, '5 10 235')
        uniq_wc_output = shell_output('%s | uniq | wc | tr -s " "' % cat)
        self.assertEqual(uniq_wc_output, '1 2 47')
        child.sendline("!rm -fr '%s'" % tmp_dir)
        child.expect('ready \(5\)> ')
        child.sendline(':quit')
        child.expect(pexpect.EOF)

