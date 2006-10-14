# from http://pdos.csail.mit.edu/~cblake/cls/cls.py

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
