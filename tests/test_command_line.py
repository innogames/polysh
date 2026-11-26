"""Polysh - Tests - Command Line

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

import os

import pexpect
import pytest


def test_good_hosts_file(polysh, tmp_path):
    hosts_file = tmp_path / 'hosts'
    hosts_file.write_text('localhost # Comment\n# Ignore me\n127.0.0.1\n')
    child = polysh([f'--hosts-file={hosts_file}'])
    child.expect(r'ready \(2\)> ')
    child.sendeof()
    child.expect(pexpect.EOF)


def test_bad_hosts_file(polysh):
    child = polysh(['--hosts-file=do not exist/at all'])
    child.expect('error')
    child.expect(pexpect.EOF)


@pytest.mark.parametrize('args', [[], ['--hosts-file=/dev/null']])
def test_no_hosts(polysh, args):
    child = polysh(args)
    child.expect('error: no hosts given')
    child.expect(pexpect.EOF)


HOSTS = 'localhost # Comment\n# Ignore me\n127.0.0.1\n'


@pytest.mark.parametrize(('args', 'count'), [
    ([], 2),
    (['--hosts-file=-'], 2),
    (['--hosts-file=-', '--hosts-file=-', 'localhost'], 3),
])
def test_hosts_from_stdin(polysh, args, count):
    child = polysh(args, piped_stdin=HOSTS)
    child.expect(rf'ready \({count}\)> ')
    # The commands are read from the terminal
    child.sendline('echo a$((6 * 7))b')
    for _ in range(count):
        child.expect('a42b')
    child.expect(rf'ready \({count}\)> ')
    child.sendeof()
    child.expect(pexpect.EOF)


def test_hosts_from_stdin_with_command(polysh):
    child = polysh(['--command=echo a$((6 * 7))b'], piped_stdin=HOSTS)
    child.expect('a42b')
    child.expect('a42b')
    child.expect(pexpect.EOF)


def test_stdin_is_the_command_when_hosts_are_given(polysh):
    child = polysh(['localhost'], piped_stdin='echo a$((6 * 7))b\n')
    child.expect('localhost : .*a42b')
    child.expect(pexpect.EOF)


def test_whitespace_separated_hosts_from_stdin(polysh):
    child = polysh([], piped_stdin='localhost\t127.0.0.1  # Comment\n')
    child.expect(r'ready \(2\)> ')
    child.sendeof()
    child.expect(pexpect.EOF)


def test_whitespace_separated_hosts_file(polysh, tmp_path):
    hosts_file = tmp_path / 'hosts'
    hosts_file.write_text('localhost 127.0.0.1\n')
    child = polysh([f'--hosts-file={hosts_file}'])
    child.expect(r'ready \(2\)> ')
    child.sendeof()
    child.expect(pexpect.EOF)


@pytest.mark.parametrize('piped_stdin', [
    'echo test > out\n',
    'x$(touch out)\n',
    'x`touch out`\n',
    'x | touch out\n',
    'x & touch out\n',
])
def test_commands_from_stdin_are_not_hosts(polysh, tmp_path, piped_stdin):
    child = polysh([], piped_stdin=piped_stdin)
    child.expect('read from stdin is not a hostname')
    child.expect(pexpect.EOF)
    assert not (tmp_path / 'out').exists()


def test_host_range_from_stdin(polysh):
    child = polysh([], piped_stdin='127.0.0.<1,1>\n')
    child.expect(r'ready \(2\)> ')
    child.sendeof()
    child.expect(pexpect.EOF)


def test_no_hosts_from_stdin(polysh):
    child = polysh([], piped_stdin='# Nothing\n')
    child.expect('error: no hosts given')
    child.expect(pexpect.EOF)


def test_hosts_from_stdin_without_terminal(polysh):
    child = polysh([], input_data=HOSTS, preexec_fn=os.setsid)
    child.expect('there is no terminal for interactive mode')
    child.expect(pexpect.EOF)


def test_profile(polysh):
    child = polysh(['--profile', 'localhost'])
    child.expect('Profiling using ')
    child.expect(r'ready \(1\)> ')
    child.sendline(':quit')
    # '798 function calls (777 primitive calls) in 0.054 seconds'
    child.expect(r' function calls (\(\d+ primitive calls\) )?in ')
    child.expect('Ordered by')
    child.expect(pexpect.EOF)


@pytest.mark.parametrize(('ssh', 'host', 'expected'), [
    ('echo message', 'localhost', ['message localhost']),
    (
        'echo The authenticity of host',
        'l',
        [
            'Closing connection',
            'Consider manually connecting or using ssh-keyscan',
        ],
    ),
    (
        'echo REMOTE HOST IDENTIFICATION HAS CHANGED',
        'l',
        [
            'Remote host identification has changed',
            'Consider manually connecting or using ssh-keyscan',
        ],
    ),
])
def test_init_error(polysh, ssh, host, expected):
    child = polysh([f'--ssh={ssh}', host])
    for line in expected:
        child.expect(line)
    child.expect(pexpect.EOF)


def test_unknown_host_is_reported(polysh):
    child = polysh(['localhost', 'unknown_host'])
    child.expect('Error talking to unknown_host')
    child.sendline(':quit')
    child.expect(pexpect.EOF)


def test_abort_errors(polysh):
    child = polysh(['--abort-errors', 'localhost', 'unknown_host'])
    child.expect('Error talking to unknown_host')
    child.expect(pexpect.EOF)


@pytest.mark.parametrize(('args', 'expected'), [
    ([], '[^@]machine'),
    (['--user=login'], 'login@machine'),
])
def test_user(polysh, args, expected):
    child = polysh(['--ssh=echo', *args, 'machine'])
    child.expect(expected)
    child.expect(pexpect.EOF)
