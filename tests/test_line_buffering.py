"""Polysh - Tests - Line Buffering

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

from tests.fake_shells import FRAGMENTING_SHELL, UNTERMINATED_SHELL


def run_polysh(polysh, shell, extra_args):
    child = polysh([
        f'--ssh={shell}',
        '--prompt=racadm>>',
        '--no-color',
        '--command=getractime',
        *extra_args,
        'host1',
    ])
    child.expect(pexpect.EOF)
    return child.before


def test_fragmented_without_line_buffering(polysh, fake_shell):
    output = run_polysh(polysh, fake_shell(FRAGMENTING_SHELL), [])
    # By default an unfinished line is printed as soon as the remote goes
    # quiet, so the echoed command is split over two prefixed lines
    assert 'host1 : ge' in output
    assert 'host1 : getractime' not in output


def test_fragmented_with_line_buffering(polysh, fake_shell):
    output = run_polysh(
        polysh, fake_shell(FRAGMENTING_SHELL), ['--line-buffering']
    )
    assert 'host1 : getractime' in output
    assert 'host1 : Wed Sep 23 19:03:18 2026' in output


def test_short_option(polysh, fake_shell):
    output = run_polysh(polysh, fake_shell(FRAGMENTING_SHELL), ['-l'])
    assert 'host1 : getractime' in output


def test_last_line_without_newline(polysh, fake_shell):
    output = run_polysh(polysh, fake_shell(UNTERMINATED_SHELL), ['-l'])
    # Held back by line buffering, but flushed when the remote goes away
    assert 'host1 : no newline here' in output
