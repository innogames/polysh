"""Polysh - Buffered Dispatcher Class

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
#
# The code is taken from http://pdos.csail.mit.edu/~cblake/cls/cls.py
# license in http://pdos.csail.mit.edu/~cblake/cls/cls_py_LICENSE reproduced
# thereafter:
# I, Charles Blake, hereby relinquish all rights to the functions
# terminal_size() and ioctl_GWINSZ() in file cls.py, located in this
# same code directory to the maximum extent applicable by this notice.
#
# These functions are provided "as is" and without any expressed or implied
# warranties, including, without limitation, the implied warranties of
# merchantibility and fitness for a particular purpose.
#
# It would be nice (but not necessary) to give me an artistic license credit
# somewhere in the licensing materials of any derivative product.


import os
from typing import Tuple, Optional


def _ioctl_GWINSZ(fd: int) -> Optional[Tuple[int, int]]:
    try:  # Discover terminal width
        import fcntl
        import termios
        import struct
        cr = struct.unpack('hh', fcntl.ioctl(fd, termios.TIOCGWINSZ, b'1234'))
    except BaseException:
        return None
    return int(cr[0]), int(cr[1])


def terminal_size() -> Tuple[int, int]:  # decide on *some* terminal size
    """Return (lines, columns)."""
    cr = _ioctl_GWINSZ(0) or _ioctl_GWINSZ(
        1) or _ioctl_GWINSZ(2)  # try open fds
    if not cr:                                                  # ...then ctty
        try:
            fd = os.open(os.ctermid(), os.O_RDONLY)
            cr = _ioctl_GWINSZ(fd)
            os.close(fd)
        except BaseException:
            pass
        if not cr:                            # env vars or finally defaults
            try:
                cr = int(os.environ['LINES']), int(os.environ['COLUMNS'])
            except BaseException:
                cr = 25, 80
    return cr[1], cr[0]         # reverse rows, cols
