"""Polysh - Tests - Prompt Regexp

Validation and runtime share compile_prompt_regexp(), so whatever it
accepts is exactly what gets matched against remote output.

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

import re

import pexpect
import pytest

from polysh.remote_dispatcher import compile_prompt_regexp


def test_plain_prompt():
    regexp = compile_prompt_regexp('racadm>>')
    assert regexp.search(b'output\nracadm>>')
    assert regexp.search(b'output\nracadm>> \t')


def test_only_matches_at_the_end():
    regexp = compile_prompt_regexp('racadm>>')
    assert not regexp.search(b'racadm>>\nmore output')


def test_bytes_only_syntax_is_rejected():
    # Valid as a str pattern, but remote output is bytes
    re.compile(r'(?u)\w+>')
    with pytest.raises(re.error):
        compile_prompt_regexp(r'(?u)\w+>')


def test_global_flag_is_rejected():
    # Valid alone, but not once wrapped in a group
    re.compile('(?i)racadm>>')
    with pytest.raises(re.error):
        compile_prompt_regexp('(?i)racadm>>')


def test_scoped_flag_is_accepted():
    regexp = compile_prompt_regexp('(?i:racadm>>)')
    assert regexp.search(b'RACADM>>')


def test_escaping_the_group_is_rejected():
    # Wrapped, 'a)|(b' would become an unanchored alternation
    with pytest.raises(re.error):
        compile_prompt_regexp('a)|(b')


def test_non_ascii_prompt():
    regexp = compile_prompt_regexp('café>')
    assert regexp.search('café>'.encode())


def test_command_line_rejects_bytes_only_syntax(polysh):
    # Used to pass the str validation, then crash on the first read
    child = polysh([r'--prompt=(?u)\w+>', 'host1'])
    child.expect('error: invalid --prompt regex')
    child.expect(pexpect.EOF)
