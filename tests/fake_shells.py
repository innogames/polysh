"""Polysh - Tests - Fake remote shells

Scripts given to polysh as --ssh in place of ssh, standing in for remotes
that are not POSIX shells.  Each is the source of a script, written to a
file by the fake_shell fixture of conftest.py.

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

# A racadm(8) like shell: it greets, then prints a prompt without any
# trailing newline and understands nothing of PS1, stty or echo.
FAKE_SHELL = '''#!/usr/bin/env python3
import sys

sys.stdout.write('Dell Remote Access Controller\\r\\nracadm>>')
sys.stdout.flush()
for line in sys.stdin:
    command = line.strip()
    if command == 'exit':
        sys.stdout.write('\\r\\nbye\\r\\n')
        sys.stdout.flush()
        break
    sys.stdout.write('\\r\\nout[%s]\\r\\nracadm>>' % command)
    sys.stdout.flush()
'''

# Same, but it does not know about exit, so polysh has to give up on it
FAKE_SHELL_NO_EXIT = FAKE_SHELL.replace("command == 'exit'", 'False')

# A racadm(8) like shell that echoes back the command it was given, in
# fragments slow enough for polysh to see an unfinished line.  This is what
# real iDRACs do, as no stty -echo can be sent to them.
FRAGMENTING_SHELL = '''#!/usr/bin/env python3
import sys
import time

sys.stdout.write('racadm>>')
sys.stdout.flush()
for line in sys.stdin:
    command = line.strip()
    if command == 'exit':
        break
    for piece in (command[:2], command[2:]):
        sys.stdout.write(piece)
        sys.stdout.flush()
        time.sleep(0.4)
    sys.stdout.write('\\r\\nWed Sep 23 19:03:18 2026\\r\\nracadm>>')
    sys.stdout.flush()
'''

# Its last line of output lacks a trailing newline, and then it goes away
UNTERMINATED_SHELL = '''#!/usr/bin/env python3
import sys

sys.stdout.write('racadm>>')
sys.stdout.flush()
for line in sys.stdin:
    if line.strip() == 'exit':
        sys.stdout.write('\\r\\nno newline here')
        sys.stdout.flush()
        break
    sys.stdout.write('\\r\\nracadm>>')
    sys.stdout.flush()
'''

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
