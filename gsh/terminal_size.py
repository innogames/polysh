# from http://pdos.csail.mit.edu/~cblake/cls/cls.py
# License in http://pdos.csail.mit.edu/~cblake/cls/cls_py_LICENSE reproduced
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

def _ioctl_GWINSZ(fd):                  #### TABULATION FUNCTIONS
    try:                                ### Discover terminal width
        import fcntl
        import termios
        import struct
        cr = struct.unpack('hh', fcntl.ioctl(fd, termios.TIOCGWINSZ, '1234'))
    except:
        return
    return cr

def terminal_size():                    ### decide on *some* terminal size
    """Return (lines, columns)."""
    cr = _ioctl_GWINSZ(0) or _ioctl_GWINSZ(1) or _ioctl_GWINSZ(2) # try open fds
    if not cr:                                                  # ...then ctty
        try:
            fd = os.open(os.ctermid(), os.O_RDONLY)
            cr = _ioctl_GWINSZ(fd)
            os.close(fd)
        except:
            pass
        if not cr:                            # env vars or finally defaults
            try:
                cr = os.environ['LINES'], os.environ['COLUMNS']
            except:
                cr = 25, 80
    return int(cr[1]), int(cr[0])         # reverse rows, cols
