"""Polysh - Tests - Displaying Names

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


class TestDisplayNames(unittest.TestCase):
    def testHole(self):
        child = launch_polysh(['--ssh=sh;:'] + ['a'] * 100)
        child.expect('ready \(100\)> ')
        child.sendline(':disable *1*')
        child.expect('ready \(81\)> ')
        child.sendline('exit')
        child.expect('ready \(0\)> ')
        child.sendline(':enable')
        child.expect('ready \(19\)> ')
        child.sendline(':purge')
        child.expect('ready \(19\)> ')
        for i in range(20, 101):
            child.sendline(':add a')
            child.expect('ready \(%d\)> ' % i)
        child.sendline(':quit')
        child.expect(pexpect.EOF)
