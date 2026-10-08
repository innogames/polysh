"""Polysh - Tests - Password File

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

from pathlib import Path

import pexpect

# A remote asking for a password before starting its shell
SSH_ARG = """--ssh=bash -c '
read -p password: -s PASSWD;
if [ "$PASSWD" = sikr3t ]; then
    bash;
else
    exit 13;
fi; #
'
""".strip()


def start(polysh, log_file, password_file):
    return polysh([
        SSH_ARG,
        f'--password-file={password_file}',
        '--debug',
        f'--log-file={log_file}',
        '1',
        '2',
    ])


def assert_password_not_logged(log_file):
    assert 'sikr3t' not in Path(log_file).read_text()


def test_good_password(polysh, log_file):
    child = start(polysh, log_file, '-')
    child.expect('Password:')
    child.sendline('sikr3t')
    child.expect(r'ready \(2\)> ')
    child.sendline(':quit')
    child.expect(pexpect.EOF)
    assert_password_not_logged(log_file)


def test_bad_password(polysh, log_file):
    child = start(polysh, log_file, '-')
    child.expect('Password:')
    child.sendline('dontknow')
    child.expect(pexpect.EOF)
    while child.isalive():
        child.wait()
    assert child.exitstatus == 13
    assert_password_not_logged(log_file)


def test_bad_password_file(polysh, log_file, tmp_path):
    password_file = tmp_path / 'passwd'
    password_file.write_text('noidea\n')
    child = start(polysh, log_file, password_file)
    child.expect(pexpect.EOF)
    while child.isalive():
        child.wait()
    assert child.exitstatus == 13
    assert_password_not_logged(log_file)


def test_good_password_file(polysh, log_file, tmp_path):
    password_file = tmp_path / 'passwd'
    password_file.write_text('sikr3t\n')
    child = start(polysh, log_file, password_file)
    child.expect(r'ready \(2\)> ')
    child.sendline(':quit')
    child.expect(pexpect.EOF)
    while child.isalive():
        child.wait()
    assert child.exitstatus == 0
    assert_password_not_logged(log_file)
