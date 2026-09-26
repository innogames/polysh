"""Polysh - Tests - The :prompt Control Command

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
import stat
import tempfile
import unittest

import pexpect

from tests import launch_polysh

# A remote that can be either kind of shell.  It starts racadm like, printing
# 'racadm>>' with no trailing newline and echoing back what it is given.
# Being told PS1="a""b<newline>" switches it to POSIX mode, where it prints
# that marker as its prompt and stops echoing.  The 'racadm' command switches
# it back, which is what a real session dropping into racadm(8) looks like.
DUAL_SHELL = r'''#!/usr/bin/env python3
import re
import sys

PS1_RE = re.compile(r'PS1="([^"]*)""(.*)$')

prompt = None  # None means racadm mode


def write(data):
    sys.stdout.write(data)
    sys.stdout.flush()


def show_prompt():
    write('racadm>>' if prompt is None else prompt + '\n')


show_prompt()
for line in sys.stdin:
    line = line.rstrip('\n')
    match = PS1_RE.search(line)
    if match:
        prompt = match.group(1) + match.group(2)
        # The closing quote of the PS1 value lands on the next input line
        show_prompt()
        continue
    if line == '"':
        continue
    command = line.strip()
    if command == 'exit':
        break
    if command == 'racadm':
        prompt = None
        show_prompt()
        continue
    if prompt is None:
        write(command)
    if command.startswith('echo '):
        write('\r\n' + command[5:])
    else:
        write('\r\nout[%s]' % command)
    write('\r\n')
    show_prompt()
'''


class TestPromptCommand(unittest.TestCase):
    def setUp(self):
        fd, self.shell = tempfile.mkstemp(prefix='polysh_fake_shell.')
        os.write(fd, DUAL_SHELL.encode())
        os.close(fd)
        os.chmod(self.shell, os.stat(self.shell).st_mode | stat.S_IXUSR)

    def tearDown(self):
        os.remove(self.shell)

    def launch(self, extra_args=()):
        child = launch_polysh(
            [f'--ssh={self.shell}', '--no-color', '-l', *extra_args, 'host1']
        )
        child.expect(r'ready \(1\)> ')
        return child

    def testSwitchToCustomPrompt(self):
        """The reason this command exists: a POSIX shell that drops into a
        remote of another kind mid-session."""
        child = self.launch()
        child.sendline('echo hello-posix')
        child.expect('hello-posix')
        child.expect(r'ready \(1\)> ')
        # Now the remote prompt is one polysh knows nothing about
        child.sendline('racadm')
        child.expect(r'waiting \(1/1\)> ')
        child.sendline(':prompt racadm>>')
        child.expect('Waiting for a prompt matching racadm>>')
        child.expect(r'ready \(1\)> ')
        child.sendline('getractime')
        child.expect(r'out\[getractime\]')
        child.expect(r'ready \(1\)> ')
        child.sendline(':quit')
        child.expect(pexpect.EOF)

    def testSwitchBackWithEmptyArgument(self):
        child = self.launch(['--prompt=racadm>>'])
        child.sendline(':prompt ""')
        child.expect('Setting PS1 on the remote shells again')
        child.expect(r'ready \(1\)> ')
        child.sendline('echo hello-posix')
        child.expect('hello-posix')
        child.expect(r'ready \(1\)> ')
        child.sendline(':quit')
        child.expect(pexpect.EOF)

    def testSwitchBackWithNoArgument(self):
        child = self.launch(['--prompt=racadm>>'])
        child.sendline(':prompt')
        child.expect('Setting PS1 on the remote shells again')
        child.expect(r'ready \(1\)> ')
        child.sendline('echo hello-posix')
        child.expect('hello-posix')
        child.expect(r'ready \(1\)> ')
        child.sendline(':quit')
        child.expect(pexpect.EOF)

    def testRoundTrip(self):
        child = self.launch(['--prompt=racadm>>'])
        child.sendline(':prompt ""')
        child.expect(r'ready \(1\)> ')
        child.sendline(':prompt racadm>>')
        child.expect('Waiting for a prompt matching')
        child.sendline('racadm')
        child.expect(r'ready \(1\)> ')
        child.sendline('getractime')
        child.expect(r'out\[getractime\]')
        child.expect(r'ready \(1\)> ')
        child.sendline(':quit')
        child.expect(pexpect.EOF)

    def testRecoverFromWrongPromptBeforeStart(self):
        """A --prompt that never matches leaves the shell not_started, with
        the remote silent at its own prompt.  :prompt must still reach it."""
        child = launch_polysh(
            [
                f'--ssh={self.shell}',
                '--no-color',
                '-l',
                '--prompt=wrong>>',
                'host1',
            ]
        )
        child.expect(r'waiting \(1/1\)> ')
        child.sendline(':prompt ""')
        child.expect('Setting PS1 on the remote shells again')
        child.expect(r'ready \(1\)> ')
        child.sendline('echo hello-posix')
        child.expect('hello-posix')
        child.expect(r'ready \(1\)> ')
        child.sendline(':quit')
        child.expect(pexpect.EOF)

    def testInvalidRegexIsRejected(self):
        child = self.launch(['--prompt=racadm>>'])
        child.sendline(':prompt racadm(>>')
        child.expect('Invalid prompt regex')
        # Valid as a str regex, but not against the bytes of remote output
        child.sendline(':prompt (?u)racadm>>')
        child.expect('Invalid prompt regex')
        # Valid alone, but not inside the group it is wrapped in
        child.sendline(':prompt (?i)racadm>>')
        child.expect('Invalid prompt regex')
        # The previous prompt still works, the bad one was not applied
        child.sendline('getractime')
        child.expect(r'out\[getractime\]')
        child.expect(r'ready \(1\)> ')
        child.sendline(':quit')
        child.expect(pexpect.EOF)

    def testCompletion(self):
        child = self.launch()
        child.send(':prom\t')
        child.expect('pt')
        child.sendline('')
        child.expect(r'ready \(1\)> ')
        child.sendline(':quit')
        child.expect(pexpect.EOF)
