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
# Copyright (c) 2006 Guillaume Chazarain <guichaz@yahoo.fr>

import fcntl
import os
import signal
import struct
import sys
import termios

from gsh.terminal_size import terminal_size

# We remember the length of the prompt in order
# to clear it with as many ' ' characters
prompt_length = 0

def set_stdin_blocking(blocking):
    """asyncore sets stdin to O_NONBLOCK, stdout/err may be duped to stdin
    so they may be set to O_NONBLOCK too. We have to clear this flag when
    printing to the console as we prefer blocking rather than having an
    exception when the console is busy"""
    stdin_fd = sys.stdin.fileno()
    flags = fcntl.fcntl(stdin_fd, fcntl.F_GETFL)
    if blocking:
        flags = flags & ~os.O_NONBLOCK
    else:
        flags = flags | os.O_NONBLOCK
    fcntl.fcntl(stdin_fd, fcntl.F_SETFL, flags)

def console_output(msg, output=sys.stdout):
    """Use instead of print, to prepare the console (clear the prompt) and
    restore it after"""
    set_stdin_blocking(True)
    global prompt_length
    print >> output, '\r', prompt_length * ' ', '\r', msg,
    prompt_length = 0
    set_stdin_blocking(False)

def show_prompt():
    """The prompt is '[available shells/alive shells]'"""
    from gsh import remote_dispatcher
    completed, total = remote_dispatcher.count_completed_processes()
    prompt = '\r[%d/%d]> ' % (completed, total)
    console_output(prompt)
    global prompt_length
    prompt_length = max(prompt_length, len(prompt))
    set_stdin_blocking(True)
    # We flush because there is no '\n' but a '\r'
    sys.stdout.flush()
    set_stdin_blocking(False)

def watch_window_size():
    """Detect when the window size changes, and propagate the new size to the
    remote shells"""
    def sigwinch(unused_signum, unused_frame):
        from gsh import remote_dispatcher
        h, w = terminal_size()
        # python bug http://python.org/sf/1112949 on amd64
        # from ajaxterm.py
        bug = struct.unpack('i', struct.pack('I', termios.TIOCSWINSZ))[0]
        packed_size = struct.pack('HHHH', w, h, 0, 0)
        for i in remote_dispatcher.all_instances():
            if i.enabled:
                fcntl.ioctl(i.fd, bug, packed_size)
    sigwinch(None, None)
    signal.signal(signal.SIGWINCH, sigwinch)
