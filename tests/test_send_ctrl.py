"""Polysh - Tests - Sending Control Characters

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

BACKSLASH = chr(92)

# A remote that names the control bytes it is sent, rather than acting on
# them.  It has to clear ISIG, or the kernel would turn those bytes into
# signals first, and ICANON, or they would sit in the line buffer until a
# newline showed up.
REPORTING_SHELL = r'''#!/usr/bin/env python3
import os
import sys
import termios

NAMES = {0x03: 'CTRL-C', 0x04: 'CTRL-D', 0x1a: 'CTRL-Z',
         0x1c: 'CTRL-BACKSLASH'}

try:
    attrs = termios.tcgetattr(0)
    attrs[3] &= ~(termios.ISIG | termios.ICANON | termios.ECHO)
    attrs[6][termios.VMIN] = 1
    attrs[6][termios.VTIME] = 0
    termios.tcsetattr(0, termios.TCSANOW, attrs)
except termios.error:
    pass


def write(data):
    os.write(1, data.encode())


write('racadm>>')
buf = b''
while True:
    chunk = os.read(0, 1024)
    if not chunk:
        break
    for byte in chunk:
        if byte in NAMES:
            write('\r\ngot[%s]\r\nracadm>>' % NAMES[byte])
            continue
        if byte in (0x0a, 0x0d):
            command = buf.decode(errors='replace').strip()
            buf = b''
            if command == 'exit':
                sys.exit(0)
            write('\r\nout[%s]\r\nracadm>>' % command)
            continue
        buf += bytes([byte])
'''


class TestSendCtrl(unittest.TestCase):
    def setUp(self):
        fd, self.shell = tempfile.mkstemp(prefix='polysh_fake_shell.')
        os.write(fd, REPORTING_SHELL.encode())
        os.close(fd)
        os.chmod(self.shell, os.stat(self.shell).st_mode | stat.S_IXUSR)

    def tearDown(self):
        os.remove(self.shell)

    def launch(self):
        child = launch_polysh(
            [
                f'--ssh={self.shell}',
                '--prompt=racadm>>',
                '--no-color',
                '-l',
                'host1',
            ]
        )
        child.expect(r'ready \(1\)> ')
        return child

    def testSendCtrlBackslash(self):
        child = self.launch()
        child.sendline(':send_ctrl ' + BACKSLASH)
        child.expect(r'got\[CTRL-BACKSLASH\]')
        child.expect(r'ready \(1\)> ')
        child.sendline(':quit')
        child.expect(pexpect.EOF)

    def testSendCtrlLetter(self):
        child = self.launch()
        child.sendline(':send_ctrl c')
        child.expect(r'got\[CTRL-C\]')
        child.expect(r'ready \(1\)> ')
        child.sendline(':send_ctrl z')
        child.expect(r'got\[CTRL-Z\]')
        child.expect(r'ready \(1\)> ')
        child.sendline(':quit')
        child.expect(pexpect.EOF)

    def testUnsendableArgumentIsReported(self):
        """This used to raise out of the dispatcher, which closed the stdin
        notification socket and killed polysh on the next prompt."""
        child = self.launch()
        child.sendline(':send_ctrl %')
        child.expect(r'Expected a letter or one of')
        child.expect(r'ready \(1\)> ')
        # Still alive and usable
        child.sendline('getractime')
        child.expect(r'out\[getractime\]')
        child.expect(r'ready \(1\)> ')
        child.sendline(':quit')
        child.expect(pexpect.EOF)

    def testLocalCtrlBackslashIsForwarded(self):
        child = self.launch()
        child.send('\x1c')
        child.expect(r'got\[CTRL-BACKSLASH\]')
        child.expect(r'ready \(1\)> ')
        child.sendline(':quit')
        child.expect(pexpect.EOF)
