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

import pexpect
import pytest

from tests.fake_shells import DUAL_SHELL


@pytest.fixture
def shell(fake_shell):
    return fake_shell(DUAL_SHELL)


def launch(polysh, shell, extra_args=()):
    child = polysh(
        [f'--ssh={shell}', '--no-color', '-l', *extra_args, 'host1']
    )
    child.expect(r'ready \(1\)> ')
    return child


def test_switch_to_custom_prompt(polysh, shell):
    """The reason this command exists: a POSIX shell that drops into a
    remote of another kind mid-session."""
    child = launch(polysh, shell)
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


@pytest.mark.parametrize('argument', ['', ' ""'])
def test_switch_back(polysh, shell, argument):
    """An empty argument, spelled out or not, gives the remote shells back
    to polysh"""
    child = launch(polysh, shell, ['--prompt=racadm>>'])
    child.sendline(':prompt' + argument)
    child.expect('Setting PS1 on the remote shells again')
    child.expect(r'ready \(1\)> ')
    child.sendline('echo hello-posix')
    child.expect('hello-posix')
    child.expect(r'ready \(1\)> ')
    child.sendline(':quit')
    child.expect(pexpect.EOF)


def test_round_trip(polysh, shell):
    child = launch(polysh, shell, ['--prompt=racadm>>'])
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


def test_recover_from_wrong_prompt_before_start(polysh, shell):
    """A --prompt that never matches leaves the shell not_started, with
    the remote silent at its own prompt.  :prompt must still reach it."""
    child = polysh([
        f'--ssh={shell}',
        '--no-color',
        '-l',
        '--prompt=wrong>>',
        'host1',
    ])
    child.expect(r'waiting \(1/1\)> ')
    child.sendline(':prompt ""')
    child.expect('Setting PS1 on the remote shells again')
    child.expect(r'ready \(1\)> ')
    child.sendline('echo hello-posix')
    child.expect('hello-posix')
    child.expect(r'ready \(1\)> ')
    child.sendline(':quit')
    child.expect(pexpect.EOF)


def test_invalid_regex_is_rejected(polysh, shell):
    child = launch(polysh, shell, ['--prompt=racadm>>'])
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


def test_completion(polysh, shell):
    child = launch(polysh, shell)
    child.send(':prom\t')
    child.expect('pt')
    child.sendline('')
    child.expect(r'ready \(1\)> ')
    child.sendline(':quit')
    child.expect(pexpect.EOF)


def test_reset_prompt_is_refused_with_a_custom_prompt(polysh, shell):
    """The remote prompt is not polysh's to reset when --prompt matches it"""
    child = launch(polysh, shell, ['--prompt=racadm>>'])
    child.sendline(':reset_prompt')
    child.expect('Not resetting the prompt of host1: it is matched with')
    child.expect(r'ready \(1\)> ')
    child.sendline(':quit')
    child.expect(pexpect.EOF)
