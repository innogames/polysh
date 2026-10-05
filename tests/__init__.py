"""Polysh - Tests

Copyright (c) 2006 Guillaume Chazarain <guichaz@gmail.com>
Copyright (c) 2024 InnoGames GmbH
"""
import os
import sys

import pexpect
from pexpect.popen_spawn import PopenSpawn


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

TESTS_DIR = os.path.dirname(os.path.abspath(__file__))

# How polysh reaches 'localhost' in the tests: a local login shell through
# fake_ssh.sh by default, so that no sshd has to be set up, or the ssh
# command template given in POLYSH_TEST_SSH, see with_sshd.sh.  Tests that
# pass their own --ssh override it, argparse keeps the last one.
#
# exec, as in the default ssh template, makes the shell polysh's direct
# child: nothing in between prints "Killed" when a test kills it, and
# polysh sees the exit the way it would see ssh leaving.
SSH = os.environ.get('POLYSH_TEST_SSH') or (
    'exec ' + os.path.join(TESTS_DIR, 'fake_ssh.sh') + ' %(host)s'
)

# The polysh of the environment running the tests, spawned directly.  Not
# through "uv run": uv stays alive as the parent and relays the terminal's
# signals to its child, so polysh would get a Ctrl-C or Ctrl-\ twice and
# the second one could hit while the first is being handled.
POLYSH = os.path.join(os.path.dirname(sys.executable), 'polysh')
if os.path.exists(POLYSH):
    POLYSH_ARGS = [POLYSH]
else:
    POLYSH_ARGS = [
        sys.executable, '-c', 'from polysh.main import main; main()'
    ]


def launch_polysh(args, input_data=None):
    args = POLYSH_ARGS + ['--ssh=' + SSH] + args

    if input_data is None:
        child = pexpect.spawn(args[0], args=args[1:], encoding='utf-8')
    else:
        child = PopenSpawn(args)
        child.send(input_data)
        child.sendeof()
    return child