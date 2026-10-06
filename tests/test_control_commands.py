"""Polysh - Tests - Control Commands

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
from time import sleep

import pexpect
import pytest


def test_empty_control_command(polysh):
    child = polysh(['localhost'])
    child.expect(r'ready \(1\)> ')
    child.sendline(':')
    child.expect(r'ready \(1\)> ')
    child.sendeof()
    child.expect(pexpect.EOF)


def test_blank_output_lines_are_dropped(polysh):
    child = polysh(['localhost'])
    child.expect(r'ready \(1\)> ')
    child.sendline('echo a; echo; echo; echo; echo; echo; echo; echo b')
    child.expect('a')
    child.expect('b')
    child.expect(r'ready \(1\)> ')
    child.sendeof()
    child.expect(pexpect.EOF)


def test_unknown_control_command(polysh):
    child = polysh(['localhost'])
    child.expect(r'ready \(1\)> ')
    child.sendline(':unknown')
    child.expect('Unknown control command: unknown')
    child.expect(r'ready \(1\)> ')
    child.sendeof()
    child.expect(pexpect.EOF)


def test_send_ctrl(polysh):
    """Completion of the letter, the argument errors, and Ctrl-Z then
    Ctrl-D sent to a running cat"""
    child = polysh(['localhost'])
    child.expect(r'ready \(1\)> ')
    child.sendline('cat')
    child.expect(r'waiting \(1/1\)> ')
    child.sendline(':send_ctrl \tz\t\t')
    child.expect(r'ready \(1\)> ')
    child.sendline(':send_ctrl')
    child.expect('Expected at least a letter')
    child.expect(r'ready \(1\)> ')
    child.sendline(':send_ctrl word')
    child.expect('Expected a single letter, got: word')
    child.expect(r'ready \(1\)> ')
    child.sendline('fg')
    child.expect(r'waiting \(1/1\)> ')
    child.sendline(':send_ctrl d')
    child.expect(r'ready \(1\)> ')
    child.sendeof()
    child.expect(pexpect.EOF)


def test_local_ctrl_c_and_ctrl_d_are_forwarded(polysh):
    # A control key typed right after Enter reaches the remote shell
    # within a millisecond of the command line, before the command has
    # started or even been read.  Wait for the command to say it owns
    # the terminal before sending it one.
    # The output line makes polysh redraw its prompt by interrupting
    # readline, and a key typed during that is lost too.  The redraw
    # settles once the remote has been quiet for 0.2s, wait that out.
    # The marker is split in the command so that the echo of the typed
    # line cannot match it, only the output can.
    child = polysh(['localhost'])
    child.expect(r'ready \(1\)> ')
    child.sendline('( echo start""ed; exec sleep 1h )')
    child.expect('started')
    sleep(0.5)
    child.expect(r'waiting \(1/1\)> ')
    child.sendcontrol('c')
    child.expect(r'ready \(1\)> ')
    child.sendline('( echo start""ed; exec cat )')
    child.expect('started')
    sleep(0.5)
    child.expect(r'waiting \(1/1\)> ')
    child.sendcontrol('d')
    child.expect(r'ready \(1\)> ')
    child.sendeof()
    child.expect(pexpect.EOF)


def test_enable_disable_and_list(polysh):
    child = polysh(['localhost'])
    child.expect(r'ready \(1\)> ')
    child.sendline('cat')
    child.expect(r'waiting \(1/1\)> ')
    child.sendline(':disabl\tlocal* not_found\t')
    child.expect('not_found not found\r\n')
    child.expect(r'ready \(0\)> ')
    child.sendline(':enable local\t')
    child.expect(r'waiting \(1/1\)> ')
    child.sendline(':list')
    child.expect('localhost enabled running:')
    child.expect(r'waiting \(1/1\)> ')
    child.sendline(':list local\t')
    child.expect('localhost enabled running:')
    child.expect(r'waiting \(1/1\)> ')
    child.sendline(':list unknown')
    child.expect('unknown not found')
    child.expect(r'waiting \(1/1\)> ')
    child.sendline(':send_ctrl c')
    child.expect(r'ready \(1\)> ')
    child.sendline(':quit')
    child.expect(pexpect.EOF)


def test_reconnect(polysh):
    child = polysh(['localhost'] * 2)
    child.expect(r'ready \(2\)> ')
    child.sendline(':disable localhost')
    child.sendline('exit')
    child.expect('exit\r\n')
    child.expect(r'ready \(0\)>')
    child.sendline(':reconnect l\t')
    child.sendline(':enable')
    child.expect(r'ready \(2\)> ')
    child.sendeof()
    child.expect(pexpect.EOF)


def test_list_manipulation(polysh):
    child = polysh(['localhost'])
    child.expect(r'ready \(1\)> ')
    child.sendline(':add localhost')
    child.expect(r'ready \(2\)> ')
    child.sendline(':rename $(echo newname)')
    child.expect(r'ready \(2\)> ')
    child.sendline('date')
    child.expect('newname')
    child.expect('newname')
    child.expect(r'ready \(2\)> ')
    child.sendline(':rename $EMPTY_VARIABLE')
    child.expect(r'ready \(2\)> ')
    child.sendline('date')
    child.expect('localhost')
    child.expect('localhost')
    child.expect(r'ready \(2\)> ')
    child.sendline(':rename $(echo newname)')
    child.expect(r'ready \(2\)> ')
    child.sendline('date')
    child.expect('newname')
    child.expect('newname')
    child.expect(r'ready \(2\)> ')
    child.sendline(':disable newname')
    child.sendline(':purge')
    child.sendline(':enable *')
    child.expect(r'ready \(1\)> ')
    child.sendline(':rename')
    child.expect(r'ready \(1\)> ')
    child.sendline('date')
    child.expect('localhost :')
    child.expect(r'ready \(1\)> ')
    child.sendeof()
    child.expect(pexpect.EOF)


def test_local_command(polysh):
    child = polysh(['localhost'])
    child.expect(r'ready \(1\)> ')
    child.sendline('cat')
    child.expect(r'waiting \(1/1\)> ')
    child.sendline('!ech\t te""st')
    child.expect('test')
    child.sendline(':send_ctrl d')
    child.expect(r'ready \(1\)> ')
    child.sendline('!exit 42')
    child.expect('Child returned 42')
    child.expect(r'ready \(1\)> ')
    child.sendline('!python -c "import os; os.kill(os.getpid(), 9)"')
    child.expect('Child was terminated by signal 9')
    child.expect(r'ready \(1\)> ')
    child.sendline(':chdir /does/not/exist')
    child.expect(r"\[Errno 2\] .*: '/does/not/exist'")
    child.sendline(':chdir /usr/sbi\t/does/not/exist')
    child.expect('/usr/sbin')
    child.expect(r'ready \(1\)> ')
    child.sendeof()
    child.expect(pexpect.EOF)


def test_local_abs_path_completion(polysh):
    child = polysh(['localhost'])
    child.expect(r'ready \(1\)> ')
    child.sendline('echo /dev/nul\t')
    child.expect('\033\\[1;36mlocalhost : \033\\[1;m/dev/null')
    child.expect(r'ready \(1\)> ')
    child.sendline('echo /sbi\t')
    child.expect('\033\\[1;36mlocalhost : \033\\[1;m/sbin/')
    child.expect(r'ready \(1\)> ')
    child.sendeof()
    child.expect(pexpect.EOF)


@pytest.mark.parametrize(('path', 'error'), [
    ('/', r"\[Errno 21\].*'/'"),
    ('/cannot_write', r"\[Errno 13\].*'/cannot_write'"),
])
def test_unusable_log_file(polysh, path, error):
    child = polysh([f'--log-file={path}', 'localhost'])
    child.expect(error)
    child.expect(pexpect.EOF)


def test_log_write_error(polysh):
    child = polysh(['--log-file=/dev/full', 'localhost'])
    child.sendline('echo something')
    child.expect('Exception while writing log: /dev/full')
    child.expect(r'\[Errno 28\]')
    child.expect(pexpect.EOF)


def test_set_log(polysh, log_file):
    child = polysh(['localhost'])

    def echo(msg):
        child.expect(r'ready \(1\)> ')
        child.sendline(f'echo {msg}')
        child.expect(f'\x1b\\[1;36mlocalhost : \x1b\\[1;m{msg}')

    echo('not logging')
    child.sendline(':set_log')
    echo('still not logging')
    child.sendline(f':set_log {log_file}')
    echo('now logging')
    echo('still logging')
    child.sendline(':set_log')
    echo('back to no logging')
    # Completed from the path minus its last character
    child.sendline(f':set_log {log_file[:-1]}\t')
    echo('appended to the log')
    child.sendline(':set_log')
    child.expect(r'ready \(1\)> ')
    child.sendline(':set_log /no-permission')
    child.expect(r"\[Errno 13\] .*: '/no-permission'")
    child.expect('Logging disabled')
    child.expect(r'ready \(1\)> ')
    child.sendeof()
    child.expect(pexpect.EOF)

    expected_log = """
> echo now logging
localhost : now logging
> echo still logging
localhost : still logging
> :set_log
> echo appended to the log
localhost : appended to the log
> :set_log
""".strip()
    log_lines = [
        line
        for line in Path(log_file).read_text().splitlines(keepends=True)
        if not line.startswith('[dbg] ')
    ]
    assert ''.join(log_lines).strip() == expected_log


def test_set_debug(polysh):
    child = polysh(['localhost'])
    child.expect(r'ready \(1\)> ')
    child.sendline(':set_debug')
    child.expect('Expected at least a letter')
    child.sendline(':set_debug word')
    child.expect("Expected 'y' or 'n', got: word")
    child.sendline(':set_debug \ty\t\t')
    child.expect(r'ready \(1\)> ')
    child.sendline('echo "te""st"')
    child.expect(r'\[dbg\] localhost\[idle\]: state => running')
    child.expect(r'\[dbg\] localhost\[running\]: <== echo "te""st"')
    child.expect(r'\[dbg\] localhost\[running\]: ==> test')
    child.expect('\033\\[1;36mlocalhost : \033\\[1;mtest')
    child.expect(r'\[dbg\] localhost\[running\]: state => idle')
    child.expect(r'ready \(1\)> ')
    child.sendeof()
    child.expect(pexpect.EOF)


def test_hide_password(polysh):
    child = polysh(['localhost'])
    child.expect(r'ready \(1\)> ')
    child.sendline('# passwordnotprotected')
    child.expect(r'ready \(1\)> ')
    child.sendline(':set_debug y')
    child.sendline(':set_log /dev/nul\t')
    child.sendline(':hide_password')
    child.expect('Debugging disabled')
    child.expect('Logging disabled')
    child.expect(r'ready \(1\)> ')
    child.sendline('# passwordprotected')
    child.expect(r'ready \(1\)> ')
    child.sendline('echo password\t')
    child.expect('passwordnotprotected')
    child.expect(r'ready \(1\)> ')
    child.sendeof()
    child.expect(pexpect.EOF)


def test_reset_prompt(polysh):
    child = polysh(['localhost'])
    child.expect(r'ready \(1\)> ')
    child.sendline('bash')
    child.sendline(':reset_prompt l\t')
    child.expect(r'ready \(1\)> ')
    child.sendline(':quit')
    child.expect(pexpect.EOF)


def test_purge(polysh):
    child = polysh(['localhost'] * 3)
    child.expect(r'ready \(3\)> ')
    child.sendline(':disable localhost#*')
    child.expect(r'ready \(1\)> ')
    child.sendline('kill -9 $$')
    child.expect(r'ready \(0\)> ')
    child.sendline(':enable')
    child.expect(r'ready \(2\)> ')
    child.sendline(':pur\t\t')
    child.expect(r'ready \(2\)> ')
    child.sendline(':list')
    child.expect('localhost#1 enabled idle:')
    child.expect('localhost#2 enabled idle:')
    child.expect(r'ready \(2\)> ')
    child.sendeof()
    child.expect(pexpect.EOF)


def test_print_read_buffer(polysh):
    child = polysh(['--ssh=echo message; sleep'] + ['2h'] * 3)
    child.expect(r'waiting \(3/3\)> ')
    child.sendline(':show_read_buffer \t*')
    for _ in range(3):
        child.expect('\033\\[1;[0-9]+m2h[ #][ 12] : \033\\[1;mmessage')
    child.expect(r'waiting \(3/3\)> ')
    child.sendintr()
    child.expect(pexpect.EOF)
