"""Polysh - Tests - Basics

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

from time import sleep

import pexpect
import pytest


def start_localhosts(polysh, nr_localhost):
    child = polysh(nr_localhost * ['localhost'])
    child.expect(rf'ready \({nr_localhost}\)> ')
    return child


@pytest.mark.parametrize('nr_localhost', [1, 2, 3])
def test_eof_quits(polysh, nr_localhost):
    child = start_localhosts(polysh, nr_localhost)
    child.sendeof()
    child.expect(pexpect.EOF)


@pytest.mark.parametrize('nr_localhost', [1, 2, 3])
def test_exit_quits(polysh, nr_localhost):
    child = start_localhosts(polysh, nr_localhost)
    child.sendline('exit')
    for _ in range(nr_localhost):
        child.expect('logout')
    child.expect(pexpect.EOF)


def test_prepend_prompt(polysh):
    child = polysh(['localhost'])
    child.expect(r'ready \(1\)> ')
    child.sendline('sleep 1')
    child.expect(r'waiting \(1/1\)> ')
    sleep(1)
    child.send('echo begin-')
    child.expect(r'ready \(1\)> ')
    child.sendline('end')
    child.expect('begin-end')
    child.expect(r'ready \(1\)> ')
    child.sendeof()
    child.expect(pexpect.EOF)


def test_error(polysh):
    child = polysh(['localhost', 'localhost'])
    child.expect(r'ready \(2\)> ')
    child.sendline('kill -9 $$')
    child.expect('Error talking to localhost')
    child.expect('Error talking to localhost')
    child.expect(pexpect.EOF)


def test_clean_exit(polysh):
    child = polysh(['localhost', 'localhost'])
    child.expect(r'ready \(2\)> ')
    child.sendeof()
    # We test for logout as this is the expected response of sending EOF to
    # a login shell
    child.expect('logout')
    child.expect('logout')
    child.expect(pexpect.EOF)
