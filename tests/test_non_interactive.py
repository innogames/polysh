"""Polysh - Tests - Non Interactive

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


def test_command(polysh):
    child = polysh(['--command=echo text', 'localhost'])
    child.expect('\033\\[1;36mlocalhost : \033\\[1;mtext')
    child.expect(pexpect.EOF)


def test_command_interrupted(polysh):
    child = polysh(['--command=echo text; cat', 'localhost'])
    child.expect('\033\\[1;36mlocalhost : \033\\[1;mtext')
    child.sendintr()
    child.expect(pexpect.EOF)


def test_single_command_from_stdin(polysh):
    child = polysh(['localhost'], input_data='echo line')
    child.expect('localhost : line')
    child.expect(pexpect.EOF)


def test_multiple_commands_from_stdin(polysh):
    commands = """
    echo first
    echo next
    echo last
    """
    child = polysh(['localhost'], input_data=commands)
    child.expect('localhost : first')
    child.expect('localhost : next')
    child.expect('localhost : last')
    child.expect(pexpect.EOF)


def test_command_and_stdin_are_incompatible(polysh):
    child = polysh(['localhost', '--command=date'], input_data='uptime')
    child.expect('--command and reading from stdin are incompatible')
    child.expect(pexpect.EOF)


@pytest.mark.parametrize(('command', 'code'), [('true', 0), ('false', 1)])
def test_exit_code(polysh, command, code):
    child = polysh([f'--command={command}'] + ['localhost'] * 5)
    child.expect(pexpect.EOF)
    while child.isalive():
        child.wait()
    assert child.exitstatus == code


def test_invalid_characters(polysh):
    child = polysh(
        ["--command=printf '%b' '\xacfoo‘bar\n'", 'localhost']
    )
    child.expect('\033\\[1;36mlocalhost : \033\\[1;m\xacfoo‘bar')
    child.expect(pexpect.EOF)
