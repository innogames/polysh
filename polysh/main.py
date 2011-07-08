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
# Copyright (c) 2006 Guillaume Chazarain <guichaz@gmail.com>

# Requires python 2.4

import asyncore
import atexit
import getpass
import locale
import optparse
import os
import signal
import sys
import termios

if sys.hexversion < 0x02040000:
        print >> sys.stderr, 'Your python version is too old (%s)' % \
                                                        (sys.version.split()[0])
        print >> sys.stderr, 'You need at least Python 2.4'
        sys.exit(1)

from polysh import remote_dispatcher
from polysh import dispatchers
from polysh.console import console_output
from polysh.stdin import the_stdin_thread
from polysh.host_syntax import expand_syntax
from polysh.version import VERSION
from polysh import control_commands

def kill_all():
    """When polysh quits, we kill all the remote shells we started"""
    for i in dispatchers.all_instances():
        try:
            os.kill(-i.pid, signal.SIGKILL)
        except OSError:
            # The process was already dead, no problem
            pass

def parse_cmdline():
    usage = '%s [OPTIONS] HOSTS...\n' % (sys.argv[0]) + \
            'Control commands are prefixed by ":". Use :help for the list'
    parser = optparse.OptionParser(usage, version='polysh ' + VERSION)
    parser.add_option('--hosts-file', type='str', action='append',
                      dest='hosts_filenames', metavar='FILE', default=[],
                      help='read hostnames from given file, one per line')
    parser.add_option('--command', type='str', dest='command', default=None,
                      help='command to execute on the remote shells',
                      metavar='CMD')
    def_ssh = 'exec ssh -oLogLevel=Quiet -t %(host)s exec bash --noprofile'
    parser.add_option('--ssh', type='str', dest='ssh', default=def_ssh,
                      metavar='SSH', help='ssh command to use [%s]' % def_ssh)
    parser.add_option('--user', type='str', dest='user', default=None,
                      help='remote user to log in as', metavar='USER')
    parser.add_option('--no-color', action='store_true', dest='disable_color',
                      help='disable colored hostnames [enabled]')
    parser.add_option('--password-file', type='str', dest='password_file',
                      default=None, metavar='FILE',
                      help='read a password from the specified file. - is ' +
                           'the tty.')
    parser.add_option('--log-file', type='str', dest='log_file',
                      help='file to log each machine conversation [none]')
    parser.add_option('--abort-errors', action='store_true', dest='abort_error',
                      help='abort if some shell fails to initialize [ignore]')
    parser.add_option('--debug', action='store_true', dest='debug',
                      help='print debugging information')
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

    if options.log_file:
        try:
            options.log_file = file(options.log_file, 'a')
        except IOError, e:
            print e
            sys.exit(1)

    if not args:
        parser.error('no hosts given')

    if options.password_file == '-':
        options.password = getpass.getpass()
    elif options.password_file is not None:
        password_file = file(options.password_file, 'r')
        options.password = password_file.readline().rstrip('\n')
    else:
        options.password = None

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
                remote_dispatcher.log('> ^%c\n' % ctrl.upper())
                control_commands.do_send_ctrl(ctrl)
                console_output('')
                the_stdin_thread.prepend_text = None
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
                raise asyncore.ExitNow(remote_dispatcher.options.exit_code)
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
    prof_file = 'polysh.prof'
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

def restore_tty_on_exit():
    fd = sys.stdin.fileno()
    old = termios.tcgetattr(fd)
    atexit.register(lambda: termios.tcsetattr(fd, termios.TCSADRAIN, old))

# We handle signals in the main loop, this way we can be signaled while
# handling a signal.
next_signal = None

def main():
    """Launch polysh"""
    locale.setlocale(locale.LC_ALL, '')
    setprocname('polysh')
    options, args = parse_cmdline()

    atexit.register(kill_all)
    signal.signal(signal.SIGPIPE, signal.SIG_DFL)
    options.command = find_non_interactive_command(options.command)
    options.exit_code = 0
    options.interactive = not options.command and sys.stdin.isatty() and \
                          sys.stdout.isatty()
    if options.interactive:
        def handler(sig, frame):
            global next_signal
            next_signal = sig
        signal.signal(signal.SIGINT, handler)
        signal.signal(signal.SIGTSTP, handler)
        restore_tty_on_exit()
    else:
      def handler(sig, frame):
        signal.signal(sig, signal.SIG_DFL)
        kill_all()
        os.kill(0, sig)
      signal.signal(signal.SIGINT, handler)

    remote_dispatcher.options = options

    hosts = []
    for arg in args:
        hosts.extend(expand_syntax(arg))

    dispatchers.create_remote_dispatchers(hosts)

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
