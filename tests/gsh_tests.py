#!/usr/bin/env python
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Library General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 59 Temple Place - Suite 330, Boston, MA 02111-1307, USA.
#
# See the COPYING file for license information.
#
# Copyright (c) 2007 Guillaume Chazarain <guichaz@gmail.com>

import os
import unittest
import sys
import optparse
import pexpect
import subprocess

import coverage

TESTS = unittest.TestSuite()

def iter_over_all_tests():
    py_files = [p for p in os.listdir('tests') if p.endswith('.py')]
    tests = list(set([p[:p.index('.')] for p in py_files]))
    for name in tests:
        module = getattr(__import__('tests.' + name), name)
        for module_content in dir(module):
            candidate = getattr(module, module_content)
            if not isinstance(candidate, type):
                continue
            if not issubclass(candidate, unittest.TestCase):
                continue
            suite = unittest.defaultTestLoader.loadTestsFromTestCase(candidate)
            for test_method in suite:
                yield test_method

def import_all_tests():
    for test in iter_over_all_tests():
        TESTS.addTest(test)

def import_specified_tests(names):
    for test in iter_over_all_tests():
        test_name = test.id().split('.')[-1]
        if test_name in names:
            names.remove(test_name)
            TESTS.addTest(test)
    if names:
        print 'Cannot find tests:', names
        sys.exit(1)

def parse_cmdline():
    usage='Usage: %s [OPTIONS...] [TESTS...]' % sys.argv[0]
    parser = optparse.OptionParser(usage=usage)
    parser.add_option('--coverage', action='store_true', dest='coverage',
                      default=False, help='include coverage tests')
    parser.add_option('--log', type='str', dest='log',
                      help='log all pexpect I/O and gsh debug info')
    parser.add_option('--python', type='str', dest='python', default='python',
                      help='python binary to use')
    options, args = parser.parse_args()
    return options, args

def remove_coverage_files():
    for filename in os.listdir('.'):
        if filename.startswith('.coverage'):
            os.remove(filename)

def end_coverage():
    coverage.the_coverage.start()
    coverage.the_coverage.collect()
    coverage.the_coverage.stop()
    modules = [p[:-3] for p in os.listdir('../gsh') if p.endswith('.py')]
    coverage.report(['../gsh/%s.py' % (m) for m in modules])
    remove_coverage_files()
    # Prevent the atexit.register(the_coverage.save) from recreating the files
    coverage.the_coverage.usecache = coverage.the_coverage.cache = None

def main():
    options, args = parse_cmdline()
    if options.coverage:
        remove_coverage_files()
    if args:
        import_specified_tests(args)
    else:
        import_all_tests()
    try:
        unittest.main(argv=[sys.argv[0], '-v'], defaultTest='TESTS')
    finally:
        if options.coverage:
            end_coverage()

class non_interactive_spawn(pexpect.spawn):
    def __init__(self, argv, input_data, *args, **kwargs):
        pexpect.spawn.__init__(self, None, *args, **kwargs)
        self.use_native_pty_fork = False
        self.argv = argv
        self.input_data = input_data
        self.command = argv[0]
        self.args = argv[1:]
        self._spawn(self.command, self.args)

    def _spawn__fork_pty(self):
        process = subprocess.Popen(self.argv, stdin=subprocess.PIPE,
                                              stdout=subprocess.PIPE,
                                              stderr=subprocess.STDOUT)

        fd = process.stdin.fileno()
        while self.input_data:
            written = os.write(fd, self.input_data)
            self.input_data = self.input_data[written:]
        process.stdin.close()
        # process will be garbage collected and process.stdout closed, so
        # use a dupped fd.
        return process.pid, os.dup(process.stdout.fileno())

def launch_gsh(args, input_data=None):
    args = ['../gsh.py'] + args
    options, unused_args = parse_cmdline()
    if options.coverage:
        args = ['./coverage.py', '-x', '-p'] + args
    args = [options.python] + args
    if options.log:
        logfile = open(options.log, 'a', 0644)
        args += ['--debug']
        print >> logfile, 'Launching:', str(args)
    else:
        logfile = None

    if input_data is None:
        child = pexpect.spawn(args[0], args=args[1:], logfile=logfile)
    else:
        child = non_interactive_spawn(args, input_data, logfile=logfile)
    return child

if __name__ == '__main__':
    main()
