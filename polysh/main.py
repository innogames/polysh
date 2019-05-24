"""Polysh - Main Utilities

Copyright (c) 2006 Guillaume Chazarain <guichaz@gmail.com>
Copyright (c) 2018 InnoGames GmbH
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

import asyncore
import atexit
import getpass
import locale
import argparse
import os
import signal
import sys
import termios
import readline
from typing import Callable, List

from polysh import remote_dispatcher
from polysh import dispatchers
from polysh import stdin
from polysh.console import console_output
from polysh.host_syntax import expand_syntax
from polysh import control_commands
from polysh import VERSION


def kill_all() -> None:
    """When polysh quits, we kill all the remote shells we started"""
    for i in dispatchers.all_instances():
        try:
            os.kill(-i.pid, signal.SIGKILL)
        except OSError:
            # The process was already dead, no problem
            pass


def parse_cmdline() -> argparse.Namespace:
    usage = '%s [OPTIONS] HOSTS...\n' % (sys.argv[0]) + \
            'Control commands are prefixed by ":".'
    parser = argparse.ArgumentParser(usage)
    parser.add_argument(
        '--hosts-file', type=str, action='append',
        dest='hosts_filenames', metavar='FILE', default=[],
        help='read hostnames from given file, one per line')
    parser.add_argument(
        '--command', type=str, dest='command', default=None,
        help='command to execute on the remote shells',
        metavar='CMD')
    def_ssh = 'exec ssh -oLogLevel=Quiet -t %(host)s %(port)s'
    parser.add_argument(
        '--ssh', type=str, dest='ssh', default=def_ssh,
        metavar='SSH', help='ssh command to use [%s]' % def_ssh)
    parser.add_argument(
        '--user', type=str, dest='user', default=None,
        help='remote user to log in as', metavar='USER')
    parser.add_argument(
        '--no-color', action='store_true', dest='disable_color',
        help='disable colored hostnames [enabled]')
    parser.add_argument(
        '--password-file', type=str, dest='password_file',
        default=None, metavar='FILE',
        help='read a password from the specified file. - is the tty.')
    parser.add_argument(
        '--log-file', type=str, dest='log_file',
        help='file to log each machine conversation [none]')
    parser.add_argument(
        '--abort-errors', action='store_true', dest='abort_error',
        help='abort if some shell fails to initialize [ignore]')
    parser.add_argument(
        '--debug', action='store_true', dest='debug',
        help='print debugging information')
    parser.add_argument(
        '--profile', action='store_true', dest='profile',
        default=False)
    parser.add_argument('host_names', nargs='*')
    args = parser.parse_args()

    for filename in args.hosts_filenames:
        try:
            hosts_file = open(filename, 'r')
            for line in hosts_file.readlines():
                if '#' in line:
                    line = line[:line.index('#')]
                line = line.strip()
                if line:
                    args.host_names.append(line)
            hosts_file.close()
        except IOError as e:
            parser.error(str(e))

    if args.log_file:
        try:
            args.log_file = open(args.log_file, 'a')
        except IOError as e:
            print(e)
            sys.exit(1)

    if not args.host_names:
        parser.error('no hosts given')

    if args.password_file == '-':
        args.password = getpass.getpass()
    elif args.password_file is not None:
        password_file = open(args.password_file, 'r')
        args.password = password_file.readline().rstrip('\n')
    else:
        args.password = None

    return args


def find_non_interactive_command(command: str) -> str:
    if sys.stdin.isatty():
        return command

    stdin = sys.stdin.read()
    if stdin and command:
        print(
            '--command and reading from stdin are incompatible',
            file=sys.stderr,
        )
        sys.exit(1)
    if stdin and not stdin.endswith('\n'):
        stdin += '\n'
    return command or stdin


def init_history(histfile: str) -> None:
    if hasattr(readline, "read_history_file"):
        try:
            readline.read_history_file(histfile)
        except IOError:
            pass


def save_history(histfile: str) -> None:
    readline.set_history_length(1000)
    readline.write_history_file(histfile)


def loop(interactive: bool) -> None:
    histfile = os.path.expanduser("~/.polysh_history")
    init_history(histfile)
    next_signal = None
    last_status = None
    while True:
        try:
            if next_signal:
                current_signal = next_signal
                next_signal = None
                sig2chr = {signal.SIGINT: 'C', signal.SIGTSTP: 'Z'}
                ctrl = sig2chr[current_signal]
                remote_dispatcher.log('> ^{}\n'.format(ctrl).encode())
                control_commands.do_send_ctrl(ctrl)
                console_output(b'')
                stdin.the_stdin_thread.prepend_text = None
            while dispatchers.count_awaited_processes()[0] and \
                    remote_dispatcher.main_loop_iteration(timeout=0.2):
                pass
            # Now it's quiet
            for r in dispatchers.all_instances():
                r.print_unfinished_line()
            current_status = dispatchers.count_awaited_processes()
            if current_status != last_status:
                console_output(b'')
            if remote_dispatcher.options.interactive:
                stdin.the_stdin_thread.want_raw_input()
            last_status = current_status
            if dispatchers.all_terminated():
                # Clear the prompt
                console_output(b'')
                raise asyncore.ExitNow(remote_dispatcher.options.exit_code)
            if not next_signal:
                # possible race here with the signal handler
                remote_dispatcher.main_loop_iteration()
        except KeyboardInterrupt:
            if interactive:
                next_signal = signal.SIGINT
            else:
                kill_all()
                os.kill(0, signal.SIGINT)
        except asyncore.ExitNow as e:
            console_output(b'')
            save_history(histfile)
            sys.exit(e.args[0])


def _profile(continuation: Callable) -> None:
    prof_file = 'polysh.prof'
    import cProfile
    import pstats
    print('Profiling using cProfile')
    cProfile.runctx('continuation()', globals(), locals(), prof_file)
    stats = pstats.Stats(prof_file)
    stats.strip_dirs()
    stats.sort_stats('time', 'calls')
    stats.print_stats(50)
    stats.print_callees(50)
    os.remove(prof_file)


def restore_tty_on_exit() -> None:
    fd = sys.stdin.fileno()
    old = termios.tcgetattr(fd)
    atexit.register(lambda: termios.tcsetattr(fd, termios.TCSADRAIN, old))


def run() -> None:
    """Launch polysh"""
    locale.setlocale(locale.LC_ALL, '')
    atexit.register(kill_all)
    signal.signal(signal.SIGPIPE, signal.SIG_DFL)

    args = parse_cmdline()

    args.command = find_non_interactive_command(args.command)
    args.exit_code = 0
    args.interactive = (
        not args.command
        and sys.stdin.isatty()
        and sys.stdout.isatty())
    if args.interactive:
        restore_tty_on_exit()

    remote_dispatcher.options = args

    hosts = []  # type: List[str]
    for host in args.host_names:
        hosts.extend(expand_syntax(host))

    dispatchers.create_remote_dispatchers(hosts)

    signal.signal(signal.SIGWINCH, lambda signum, frame:
                  dispatchers.update_terminal_size())

    stdin.the_stdin_thread = stdin.StdinThread(args.interactive)

    if args.profile:
        def safe_loop() -> None:
            try:
                loop(args.interactive)
            except BaseException:
                pass
        _profile(safe_loop)
    else:
        loop(args.interactive)


def main():
    """Wrapper around run() to setup sentry"""

    sentry_dsn = os.environ.get('POLYSH_SENTRY_DSN')

    if sentry_dsn:
        from raven import Client
        client = Client(
            dsn=sentry_dsn,
            release='.'.join(map(str, VERSION)),
            ignore_exceptions=[
                KeyboardInterrupt
            ]
        )

        try:
            run()
        except Exception:
            client.captureException()

    else:
        run()
