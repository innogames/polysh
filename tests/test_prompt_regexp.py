"""Polysh - Tests - Prompt Regexp Compilation

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
import unittest

import pexpect

from polysh.remote_dispatcher import compile_prompt_regexp
from tests import launch_polysh


class TestCompilePromptRegexp(unittest.TestCase):
    """Validation and runtime share compile_prompt_regexp(), so whatever it
    accepts is exactly what gets matched against remote output."""

    def testPlainPrompt(self):
        regexp = compile_prompt_regexp('racadm>>')
        self.assertTrue(regexp.search(b'output\nracadm>>'))
        self.assertTrue(regexp.search(b'output\nracadm>> \t'))

    def testOnlyMatchesAtTheEnd(self):
        regexp = compile_prompt_regexp('racadm>>')
        self.assertFalse(regexp.search(b'racadm>>\nmore output'))

    def testBytesOnlySyntaxIsRejected(self):
        # Valid as a str pattern, but remote output is bytes
        re.compile(r'(?u)\w+>')
        with self.assertRaises(re.error):
            compile_prompt_regexp(r'(?u)\w+>')

    def testGlobalFlagIsRejected(self):
        # Valid alone, but not once wrapped in a group
        re.compile('(?i)racadm>>')
        with self.assertRaises(re.error):
            compile_prompt_regexp('(?i)racadm>>')

    def testScopedFlagIsAccepted(self):
        regexp = compile_prompt_regexp('(?i:racadm>>)')
        self.assertTrue(regexp.search(b'RACADM>>'))

    def testEscapingTheGroupIsRejected(self):
        # Wrapped, 'a)|(b' would become an unanchored alternation
        with self.assertRaises(re.error):
            compile_prompt_regexp('a)|(b')

    def testNonAsciiPrompt(self):
        regexp = compile_prompt_regexp('café>')
        self.assertTrue(regexp.search('café>'.encode()))


class TestPromptRegexpValidation(unittest.TestCase):
    def testCommandLineRejectsBytesOnlySyntax(self):
        # Used to pass the str validation, then crash on the first read
        child = launch_polysh([r'--prompt=(?u)\w+>', 'host1'])
        child.expect('error: invalid --prompt regex')
        child.expect(pexpect.EOF)
