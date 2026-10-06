"""Polysh - Tests - Fixtures

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
import signal
import sys

import pexpect
import pytest
from pexpect.popen_spawn import PopenSpawn

TESTS_DIR = os.path.dirname(os.path.abspath(__file__))


class _PopenSpawn(PopenSpawn):
    """PopenSpawn raises EOF once the output is drained but neither waits
    for the process nor closes the pipe, so Popen warns at garbage
    collection about a still running subprocess and an unclosed file.
    Do both as soon as EOF is seen."""

    def read_nonblocking(self, size=1, timeout=-1):
        try:
            return super().read_nonblocking(size, timeout)
        except pexpect.EOF:
            self.wait()
            self.proc.stdout.close()
            raise


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


def _kill(child):
    """Get rid of a polysh left behind by a failed test, and of the remote
    shells it started, which polysh kills in its atexit handler"""
    if isinstance(child, PopenSpawn):
        if child.proc.poll() is None:
            child.kill(signal.SIGKILL)
            child.proc.wait()
        child.proc.stdout.close()
    else:
        if child.isalive():
            child.terminate(force=True)
        child.close()


@pytest.fixture
def polysh(tmp_path):
    """Factory spawning polysh under pexpect: polysh(args) gives a child
    talking to a pty, polysh(args, input_data) one fed through a pipe, as
    a non interactive run reading its commands from stdin.

    HOME is the test's own directory: polysh reads and writes
    ~/.polysh_history, tests running in parallel must not share it, and
    readline must not pick up the developer's ~/.inputrc.  The cwd too, so
    that --profile's polysh.prof does not land in the repository.
    Whatever a test leaves running is killed at teardown."""
    children = []
    env = dict(os.environ, HOME=str(tmp_path))

    def launch(args, input_data=None):
        args = POLYSH_ARGS + ['--ssh=' + SSH] + list(args)
        if input_data is None:
            child = pexpect.spawn(
                args[0],
                args=args[1:],
                encoding='utf-8',
                env=env,
                cwd=str(tmp_path),
            )
        else:
            child = _PopenSpawn(args, env=env, cwd=str(tmp_path))
            child.send(input_data)
            child.sendeof()
        children.append(child)
        return child

    yield launch

    for child in children:
        try:
            _kill(child)
        except Exception:
            # Cleaning up must not hide what the test itself reported
            pass


@pytest.fixture
def fake_shell(tmp_path):
    """Factory writing a stand-in for a remote shell, a script given as
    --ssh, and returning its path.  See tests/fake_shells.py."""
    counter = [0]

    def write(source):
        counter[0] += 1
        path = tmp_path / f'fake_shell_{counter[0]}.py'
        path.write_text(source)
        path.chmod(0o700)
        return str(path)

    return write


@pytest.fixture
def log_file(tmp_path):
    """Where a test may tell polysh to log, private to the test"""
    return str(tmp_path / 'polysh_test.log')
