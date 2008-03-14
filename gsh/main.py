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
# Copyright (c) 2006, 2007, 2008 Guillaume Chazarain <guichaz@gmail.com>

# Requires python 2.4

import asyncore
import atexit
import locale
import optparse
import os
import signal
import sys

if sys.hexversion < 0x02040000:
        print >> sys.stderr, 'Your python version is too old (%s)' % \
                                                        (sys.version.split()[0])
        print >> sys.stderr, 'You need at least Python 2.4'
        sys.exit(1)

from gsh import remote_dispatcher
from gsh import dispatchers
from gsh.console import console_output
from gsh.stdin import the_stdin_thread, ignore_sigchld
from gsh.host_syntax import expand_syntax
from gsh.version import VERSION
from gsh import control_commands

def kill_all():
    """When gsh quits, we kill all the remote shells we started"""
    for i in dispatchers.all_instances():
        try:
            os.kill(i.pid, signal.SIGKILL)
        except OSError:
            # The process was already dead, no problem
            pass

def parse_cmdline():
    usage = '%s [OPTIONS] HOSTS...\n' % (sys.argv[0]) + \
            'Control commands are prefixed by ":". Use :help for the list'
    parser = optparse.OptionParser(usage, version='gsh ' + VERSION)
    parser.add_option('--hosts-file', type='str', action='append',
                      dest='hosts_filenames', metavar='FILE', default=[],
                      help='read hostnames from given file, one per line')
    parser.add_option('--command', type='str', dest='command', default=None,
                      help='command to execute on the remote shells',
                      metavar='CMD')
    parser.add_option('--ssh', type='str', dest='ssh',
                      default='ssh -t %(host)s sh', metavar='SSH',
                      help='ssh command to use [ssh -t %(host)s sh]')
    parser.add_option('--abort-errors', action='store_true', dest='abort_error',
                      help='abort if some shell fails to initialize [ignore]')
    parser.add_option('--debug', action='store_true', dest='debug',
                      help='print debugging information.')
    parser.add_option('--profile', action='store_true', dest='profile',
                      default=False, help=optparse.SUPPRESS_HELP)

    options, args = parser.parse_args()
    for filename in options.hosts_filenames:
        try:
            hosts_file = open(filename, 'r')
            for line in hosts_file.readlines():
                if '#' in line:
                    line = line[:line.index('#')]
                line = line.strip()
                if line:
                    args.append(line)
            hosts_file.close()
        except IOError, e:
            parser.error(e)

    if not args:
        parser.error('no hosts given')

    return options, args

def find_non_interactive_command(command):
    if sys.stdin.isatty():
        return command

    stdin = sys.stdin.read()
    if stdin and command:
        print >> sys.stderr, '--command and reading from stdin are incompatible'
        sys.exit(1)
    if stdin and not stdin.endswith('\n'):
        stdin += '\n'
    return command or stdin

def main_loop():
    global next_signal
    last_status = None
    while True:
        try:
            if next_signal:
                current_signal = next_signal
                next_signal = None
                sig2chr = {signal.SIGINT: 'c', signal.SIGTSTP: 'z'}
                ctrl = sig2chr[current_signal]
                waited_data = control_commands.do_send_ctrl(ctrl)
                for i in dispatchers.all_instances():
                    i.read_buffer = ''
                console_output('')
            while dispatchers.count_awaited_processes()[0] and \
                  remote_dispatcher.main_loop_iteration(timeout=0.2):
                pass
            # Now it's quiet
            for r in dispatchers.all_instances():
                r.print_unfinished_line()
            current_status = dispatchers.count_awaited_processes()
            if current_status != last_status:
                console_output('')
            if remote_dispatcher.options.interactive:
                the_stdin_thread.want_raw_input()
            last_status = current_status
            if dispatchers.all_terminated():
                # Clear the prompt
                console_output('')
                raise asyncore.ExitNow(0)
            if not next_signal:
                # possible race here with the signal handler
                remote_dispatcher.main_loop_iteration()
        except asyncore.ExitNow, e:
            console_output('')
            sys.exit(e.args[0])

def setprocname(name):
    # From comments on http://davyd.livejournal.com/166352.html
    try:
        # For Python-2.5
        import ctypes
        libc = ctypes.CDLL(None)
        # Linux 2.6 PR_SET_NAME
        if libc.prctl(15, name, 0, 0, 0):
            # BSD
            libc.setproctitle(name)
    except:
        try:
            # For 32 bit
            import dl
            libc = dl.open(None)
            name += '\0'
            # Linux 2.6 PR_SET_NAME
            if libc.call('prctl', 15, name, 0, 0, 0):
                # BSD
                libc.call('setproctitle', name)
        except:
            pass

def _profile(continuation):
    prof_file = 'gsh.prof'
    try:
        import cProfile
        import pstats
        print 'Profiling using cProfile'
        cProfile.runctx('continuation()', globals(), locals(), prof_file)
        stats = pstats.Stats(prof_file)
    except ImportError:
        import hotshot
        import hotshot.stats
        prof = hotshot.Profile(prof_file, lineevents=1)
        print 'Profiling using hotshot'
        prof.runcall(continuation)
        prof.close()
        stats = hotshot.stats.load(prof_file)
    stats.strip_dirs()
    stats.sort_stats('time', 'calls')
    stats.print_stats(50)
    stats.print_callees(50)
    os.remove(prof_file)

# We handle signals in the main loop, this way we can be signaled while
# handling a signal.
next_signal = None

def main():
    """Launch gsh"""
    locale.setlocale(locale.LC_ALL, '')
    setprocname('gsh')
    options, args = parse_cmdline()

    atexit.register(kill_all)
    ignore_sigchld(True) # Don't create zombies
    signal.signal(signal.SIGPIPE, signal.SIG_DFL)
    options.command = find_non_interactive_command(options.command)
    options.interactive = not options.command and sys.stdin.isatty() and \
                          sys.stdout.isatty()
    if options.interactive:
        def handler(sig, frame):
            global next_signal
            next_signal = sig
        signal.signal(signal.SIGINT, handler)
        signal.signal(signal.SIGTSTP, handler)
    else:
        signal.signal(signal.SIGINT, signal.SIG_DFL)

    remote_dispatcher.options = options

    for arg in args:
        for host in expand_syntax(arg):
            remote_dispatcher.remote_dispatcher(host)

    signal.signal(signal.SIGWINCH, lambda signum, frame:
                                            dispatchers.update_terminal_size())

    the_stdin_thread.activate(options.interactive)

    if options.profile:
        def safe_main_loop():
            try:
                main_loop()
            except:
                pass
        _profile(safe_main_loop)
    else:
        main_loop()
