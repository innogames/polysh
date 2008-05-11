#!/usr/bin/env python
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
# Copyright (c) 2007, 2008 Guillaume Chazarain <guichaz@gmail.com>
#
# This file should remain compatible with python-1.5.2
#

import os
import popen2
import random
import signal
import socket
import string
import sys
import termios
import time
from threading import Event, Thread
from Queue import Queue

UNITS = ['B', 'KiB', 'MiB', 'GiB', 'TiB', 'PiB', 'EiB']
MAX_BUFFER_SIZE = 1024 * 1024

def human_unit(size):
    """Return a string of the form '12.34 MiB' given a size in bytes."""
    for i in xrange(len(UNITS) - 1, 0, -1):
        base = 2 ** (10 * i)
        if 2 * base < size:
            return '%.2f %s' % ((float(size) / base), UNITS[i])
    return str(size) + ' ' + UNITS[0]


def rstrip_char(string, char):
    while string and string[-1] == char:
        string = string[:-1]
    return string

class bandwidth_monitor(Thread):
    def __init__(self):
        Thread.__init__(self)
        self.setDaemon(1)
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
        print 'Done transferring %d bytes' % (self.size)

MAX_QUEUE_SIZE = 4 * 1024 * 1024
MAX_QUEUE_ITEM_SIZE = 64 * 1024

class Forwarder(Thread):
    def __init__(self, output):
        Thread.__init__(self)
        self.output = output
        self.pending = Queue(MAX_QUEUE_SIZE / MAX_QUEUE_ITEM_SIZE)
        self.start()

    def run(self):
        while True:
            data = self.pending.get()
            if data is None:
                # EOF
                self.output.close()
                break
            self.output.write(data)

    def add_data(self, data):
        self.pending.put(data)

def forward(input_file, output_files, bandwidth=False):
    forwarders = []
    for output in output_files:
        forwarders.append(Forwarder(output))
    if bandwidth:
        bw = bandwidth_monitor()

    while True:
        data = input_file.read(MAX_QUEUE_ITEM_SIZE)
        if data:
            if bandwidth:
                bw.add_transferred_size(len(data))
            for forwarder in forwarders:
                forwarder.add_data(data)
        else:
            for forwarder in forwarders:
                forwarder.add_data(None)
            break
    input_file.close()
    for forwarder in forwarders:
        forwarder.join()
    if bandwidth:
        bw.finish()

def init_listening_socket(gsh_prefix):
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.bind(('', 0))
    s.listen(5)
    host = socket.gethostname()
    port = s.getsockname()[1]
    prefix = string.join(gsh_prefix, '')
    if prefix:
        prefix = prefix + ' '
    print '%s%s:%s' % (prefix, host, port)
    return s

def get_destination():
    fd = sys.stdin.fileno()
    old_settings = termios.tcgetattr(fd)
    new_settings = termios.tcgetattr(fd)
    new_settings[3] = new_settings[3] & ~2 # 3:lflags 2:ICANON
    new_settings[6][6] = '\000' # Set VMIN to zero for lookahead only
    termios.tcsetattr(fd, 1, new_settings) # 1:TCSADRAIN
    line = ''
    while 1:
        c = os.read(sys.stdin.fileno(), 1)
        if c == '\n':
            break
        line = line + c
    termios.tcsetattr(fd, 1, old_settings) # 1:TCSADRAIN
    split = string.split(line, ':', 1)
    host = split[0]
    port = int(split[1])
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.connect((host, port))
    return s.makefile()

def shell_quote(s):
    return "'" + string.replace(s, "'", "'\\''") + "'"

def do_send(nr_peers, path):
    split = os.path.split(rstrip_char(path, '/'))
    dirname, basename = split
    if dirname:
        os.chdir(dirname)
    if not basename:
        basename = '/'
    stdout, stdin = popen2.popen2('tar c %s' % shell_quote(basename))
    stdin.close()
    forward(stdout, [get_destination()])

def do_forward(nr_peers, gsh_prefix):
    listening_socket = init_listening_socket(gsh_prefix)
    stdout, stdin = popen2.popen2('tar x')
    stdout.close()
    conn, addr = listening_socket.accept()
    forward(conn.makefile(), [get_destination(), stdin])

def do_receive(nr_peers, gsh_prefix):
    listening_socket = init_listening_socket(gsh_prefix)
    stdout, stdin = popen2.popen2('tar x')
    stdout.close()
    conn, addr = listening_socket.accept()
    # Only the last item in the chain displays the progress information
    # as it should be the last one to finish.
    forward(conn.makefile(), [stdin], bandwidth=True)

# Usage:
#
# pity.py NR_PEERS send PATH
# => reads host:port on stdin
#
# pity.py NR_PEERS forward [GSH1...]
# => reads host:port on stdin and prints listening host:port on stdout
# prefixed by GSH1...
#
# pity.py NR_PEERS receive [GSH1...]
# => prints listening host:port on stdout prefixed by GSH1...
#
def main():
    signal.signal(signal.SIGINT, lambda sig, frame: os.kill(0, signal.SIGKILL))
    nr_peers = int(sys.argv[1])
    cmd = sys.argv[2]
    if cmd == 'send' and len(sys.argv) >= 4:
        do_send(nr_peers, sys.argv[3])
    elif cmd == 'forward' and len(sys.argv) >= 3:
        do_forward(nr_peers, sys.argv[3:])
    elif cmd == 'receive' and len(sys.argv) >= 3:
        do_receive(nr_peers, sys.argv[3:])
    else:
        print 'Unknown command:', sys.argv
        sys.exit(1)

if __name__ == '__main__':
    main()

