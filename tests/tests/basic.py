"""Polysh - Tests - Basics

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


class TestBasic(unittest.TestCase):
    def localhost(self, nr_localhost):
        args = nr_localhost * ['localhost']

        def start_child():
            child = launch_polysh(args)
            child.expect('ready \(%d\)> ' % (nr_localhost))
            return child

        def test_eof():
            child = start_child()
            child.sendeof()
            child.expect(pexpect.EOF)

        def test_exit():
            child = start_child()
            child.sendline('exit')
            for i in range(nr_localhost):
                child.expect('logout')
            child.expect(pexpect.EOF)

        test_eof()
        test_exit()

    def testLocalhost(self):
        self.localhost(1)

    def testLocalhostLocalhost(self):
        self.localhost(2)

    def testLocalhostLocalhostLocalhost(self):
        self.localhost(3)

    def testPrependPrompt(self):
        child = launch_polysh(['localhost'])
        child.expect('ready \(1\)> ')
        child.sendline('sleep 1')
        child.expect('waiting \(1/1\)> ')
        child.send('echo begin-')
        child.expect('ready \(1\)> ')
        child.sendline('end')
        child.expect('begin-end')
        child.expect('ready \(1\)> ')
        child.sendeof()
        child.expect(pexpect.EOF)

    def testError(self):
        child = launch_polysh(['localhost', 'localhost'])
        child.expect('ready \(2\)> ')
        child.sendline('kill -9 $$')
        child.expect('Error talking to localhost')
        child.expect('Error talking to localhost')
        child.expect(pexpect.EOF)

    def testCleanExit(self):
        child = launch_polysh(['localhost', 'localhost'])
        child.expect('ready \(2\)> ')
        child.sendeof()
        # We test for logout as this is the expected response of sending EOF to
        # a non login shell
        idx = child.expect(['Error talking to localhost', 'logout'])
        self.assertEqual(idx, 1)
        idx = child.expect(['Error talking to localhost', pexpect.EOF])
        self.assertEqual(idx, 1)
