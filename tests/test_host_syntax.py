"""Polysh - Tests - Host Syntax

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

import pexpect
import pytest


@pytest.mark.parametrize(('pattern', 'expanded'), [
    ('0.0.0.<0-10>', [f'0.0.0.{i}' for i in range(11)]),
    ('0.0.0.<00-10>', [f'0.0.0.{i:02d}' for i in range(11)]),
    ('0.0.0.<1-10>', [f'0.0.0.{i}' for i in range(1, 11)]),
    ('0.0.0.<10-1>', [f'0.0.0.{i}' for i in range(1, 11)]),
    ('0.0.0.<01-10>', [f'0.0.0.{i:02d}' for i in range(1, 11)]),
    (
        '0.0.<1-4>.<01-03>',
        [f'0.0.{i}.{j:02d}' for i in range(1, 5) for j in range(1, 4)],
    ),
    ('0.0.0.<1>', ['0.0.0.1']),
    ('0.0.0.<1,3-5>', ['0.0.0.1', '0.0.0.3', '0.0.0.4', '0.0.0.5']),
])
def test_host_syntax(polysh, pattern, expanded):
    child = polysh([pattern, 'localhost'])
    child.expect('ready')
    child.sendline(':list')
    with_spaces = [e.replace('.', '\\.') + ' ' for e in expanded]
    for _ in range(len(expanded)):
        found = child.expect(with_spaces)
        del with_spaces[found]
    child.expect('ready')
    child.sendeof()
    child.expect(pexpect.EOF)
