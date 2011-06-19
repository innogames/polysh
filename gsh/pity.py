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
#

import binascii
import os
import signal
import socket
import string
import subprocess
import sys
import termios
import time
from threading import Event, Thread
from Queue import Queue

# Somewhat protect the stdin, be sure we read what has been sent by gsh, and
# not some garbage entered by the user.
STDIN_PREFIX = '!?^%!'

UNITS = ['B', 'KiB', 'MiB', 'GiB', 'TiB', 'PiB', 'EiB']

BASE64_TERMINATOR = '.'

def human_unit(size):
    """Return a string of the form '12.34 MiB' given a size in bytes."""
    for i in xrange(len(UNITS) - 1, 0, -1):
        base = 2.0 ** (10 * i)
        if 2 * base < size:
            return '%.2f %s' % ((float(size) / base), UNITS[i])
    return str(size) + ' ' + UNITS[0]


class bandwidth_monitor(Thread):
    def __init__(self):
        Thread.__init__(self)
        self.setDaemon(True)
        self.main_done = Event()
        self.size = 0
        self.start()

    def add_transferred_size(self, size):
        self.size = self.size + size

    def finish(self):
        self.main_done.set()
        self.join()

    def run(self):
        previous_size = 0
        previous_sampling_time = time.time()
        previous_bandwidth = 0
        while not self.main_done.isSet():
            current_size = self.size
            current_sampling_time = time.time()
            current_bandwidth = (current_size - previous_size) / \
                                (current_sampling_time - previous_sampling_time)
            current_bandwidth = (2*current_bandwidth + previous_bandwidth) / 3.0
            if current_bandwidth < 1:
                current_bandwidth = 0
            print '%s transferred at %s/s' % (human_unit(current_size),
                                              human_unit(current_bandwidth))
            previous_size = current_size
            previous_sampling_time = current_sampling_time
            previous_bandwidth = current_bandwidth
            self.main_done.wait(1.0)
        print 'Done transferring %s bytes (%s)' % (self.size,
                                                   human_unit(self.size))

def write_fully(fd, data):
    while data:
        written = os.write(fd, data)
        data = data[written:]


class Reader(object):
    def __init__(self, input_file):
        self.input_file = input_file
        self.fd = input_file.fileno()

    def close(self):
        return self.input_file.close()


class Base64Reader(Reader):
    def __init__(self, input_file):
        super(Base64Reader, self).__init__(input_file)
        self.buffer = ''
        self.eof_found = False

    def read(self):
        while True:
            if self.eof_found:
                assert not self.buffer, self.buffer
                return None

            piece = os.read(self.fd, 77 * 1024)
            if BASE64_TERMINATOR in piece[-4:]:
                self.eof_found = True
                piece = piece[:piece.index(BASE64_TERMINATOR)]
            self.buffer += piece.replace('\n', '')
            if len(self.buffer) % 4:
                end_offset = 4 * (len(self.buffer) // 4)
                to_decode = self.buffer[:end_offset]
                self.buffer = self.buffer[end_offset:]
            else:
                to_decode = self.buffer
                self.buffer = ''
            if to_decode:
                return binascii.a2b_base64(to_decode)


class FileReader(Reader):
    def __init__(self, input_file):
        super(FileReader, self).__init__(input_file)

    def read(self):
        return os.read(self.fd, 32 * 1024)


def forward(reader, output_files, print_bw):
    if print_bw:
        bw = bandwidth_monitor()

    output_fds = [output_file.fileno() for output_file in output_files]

    while True:
        data = reader.read()
        if not data:
            break
        if print_bw:
            bw.add_transferred_size(len(data))
        for output_fd in output_fds:
            write_fully(output_fd, data)

    if print_bw:
        bw.finish()

    reader.close()
    for output_file in output_files:
        output_file.close()

def init_listening_socket(gsh1, gsh2):
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.bind(('', 0))
    s.listen(5)
    host = socket.gethostname()
    port = s.getsockname()[1]
    print '%s%s%s:%s' % (gsh1, gsh2, host, port)
    return s


def pipe_to_untar():
    p = subprocess.Popen(['tar', 'x'],
                         stdin=subprocess.PIPE,
                         stdout=None,
                         close_fds=True)

    return p.stdin

def new_connection(host_port):
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    host, port_str = host_port.split(':')
    s.connect((host, int(port_str)))
    return s.makefile('r+b')


def do_replicate(destinations, print_bw):
    connections = [new_connection(host_port) for host_port in destinations]
    forward(FileReader(sys.stdin), connections, print_bw)


def do_upload(destinations, print_bw):
    untar = pipe_to_untar()
    connections = [new_connection(host_port) for host_port in destinations]
    forward(Base64Reader(sys.stdin), [untar] + connections, print_bw)


def do_forward(gsh1, gsh2, destinations, print_bw):
    listening_socket = init_listening_socket(gsh1, gsh2)
    untar = pipe_to_untar()
    connections = [new_connection(host_port) for host_port in destinations]
    conn, addr = listening_socket.accept()
    forward(FileReader(conn), [untar] + connections, print_bw)


# Usage:
#
# pity.py [--print-bw] replicate host:port...
# => reads data on stdin and forwards it to the optional list of host:port
#
# pity.py [--print-bw] upload host:port...
# => reads base64 on stdin and forwards it to the optional list of host:port
#
# pity.py [--print-bw] forward GSH1 GSH2 host:port...
# => prints listening host:port on stdout prefixed by GSH1GSH2 and forwards from
# this port to the optional list of host:port
#
def main():
    signal.signal(signal.SIGINT, lambda sig, frame: os.kill(0, signal.SIGKILL))
    if sys.argv[1] == '--print-bw':
        print_bw = True
        argv = sys.argv[2:]
    else:
        print_bw = False
        argv = sys.argv[1:]
    cmd = argv[0]
    try:
        if cmd == 'replicate':
            do_replicate(argv[1:], print_bw)
        elif cmd == 'upload':
            do_upload(argv[1:], print_bw)
        elif cmd == 'forward' and len(argv) >= 3:
            do_forward(argv[1], argv[2], argv[3:], print_bw)
        else:
            print 'Unknown command:', argv
            sys.exit(1)
    except OSError, e:
        print e
        sys.exit(1)


if __name__ == '__main__':
    main()
