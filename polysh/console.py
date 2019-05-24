"""Polysh - Console Utilities

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

import errno
import os
from typing import Optional

# We remember the length of the last printed status in order to
# clear it with ' ' characters
last_status_length = None


def safe_write(buf: bytes) -> None:
    """We can get a SIGWINCH when printing, which will cause write to raise
    an EINTR. That's not a reason to stop printing."""
    while True:
        try:
            os.write(1, buf)
            break
        except IOError as e:
            if e.errno != errno.EINTR:
                raise


def console_output(msg: bytes, logging_msg: Optional[bytes] = None) -> None:
    """Use instead of print, to clear the status information before printing"""
    from polysh import remote_dispatcher

    remote_dispatcher.log(logging_msg or msg)
    if remote_dispatcher.options.interactive:
        from polysh.stdin import the_stdin_thread
        the_stdin_thread.no_raw_input()
        global last_status_length
        if last_status_length:
            safe_write('\r{}\r'.format(
                last_status_length * ' ').encode())
            last_status_length = 0
    safe_write(msg)


def set_last_status_length(length: int) -> None:
    """The length of the prefix to be cleared when printing something"""
    global last_status_length
    last_status_length = length
