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
# Copyright (c) 2007, 2008 Guillaume Chazarain <guichaz@yahoo.fr>

import asyncore
import os
import popen2
import random
import signal
import socket
import sys
import termios
import threading
import time

UNITS = ['B', 'KiB', 'MiB', 'GiB', 'TiB', 'PiB', 'EiB']
MAX_BUFFER_SIZE = 1024 * 1024

def human_unit(size):
    """Return a string of the form '12.34 MiB' given a size in bytes."""
    for i in xrange(len(UNITS) - 1, 0, -1):
        base = 2 ** (10 * i)
        if 2 * base < size:
            return '%.2f %s' % ((float(size) / base), UNITS[i])
    return str(size) + ' ' + UNITS[0]


class bandwidth_monitor(object):
    def __init__(self, nr_peers):
        self.nr_peers = nr_peers
        self.thread = threading.Thread(target=self.run_thread)
        self.thread.setDaemon(True)
        self.main_done = threading.Event()
        self.thread_done = threading.Event()
        self.size = 0
        self.thread.start()

    def add_transferred_size(self, size):
        self.size += size

    def finish(self):
        self.main_done.set()
        self.thread_done.wait()

    def run_thread(self):
        previous_size = 0
        previous_sampling_time = time.time()
        previous_bandwidth = 0
        time.sleep(random.random() * self.nr_peers)
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
            self.main_done.wait(self.nr_peers / 2.0)
        print 'Done transferring %d bytes' % (self.size)
        self.thread_done.set()

class Transmitter(asyncore.file_dispatcher):
    def __init__(self, output_fd, forwarder):
        asyncore.file_dispatcher.__init__(self, output_fd)
        self.forwarder = forwarder
        self.buffer = ''
        self.finished = False

    def readable(self):
        return False

    def writable(self):
        return self.buffer != ''

    def setFinished(self):
        self.finished = True
        if not self.writable():
            try:
                self.close()
            except OSError:
                pass

    def handle_write(self):
        num_sent = self.send(self.buffer)
        self.buffer = self.buffer[num_sent:]
        self.forwarder.refill_output_buffers()
        if self.finished and not self.writable():
            self.close()

    def buffer_remaining_capacity(self):
        return MAX_BUFFER_SIZE - len(self.buffer)

    def add_to_buffer(self, data):
        self.buffer += data
        assert len(self.buffer) <= MAX_BUFFER_SIZE

class Forwarder(asyncore.file_dispatcher):
    def __init__(self, nr_peers, fd_input, fd_outputs):
        asyncore.file_dispatcher.__init__(self, fd_input)
        self.buffer = ''
        self.outputs = [Transmitter(fd, self) for fd in fd_outputs]
        self.bw = bandwidth_monitor(nr_peers)

    def handle_expt(self):
        self.handle_close()

    def readable(self):
        return len(self.buffer) < MAX_BUFFER_SIZE

    def writable(self):
        return False

    def handle_close(self):
        try:
            self.close()
        except OSError:
            pass
        for t in self.outputs:
            t.setFinished()

    def handle_read(self):
        capacity = MAX_BUFFER_SIZE - len(self.buffer)
        self.buffer += self.recv(capacity)
        self.refill_output_buffers()

    def refill_output_buffers(self):
        capacity = min([t.buffer_remaining_capacity() for t in self.outputs])
        if not capacity:
            return
        data = self.buffer[:capacity]
        self.bw.add_transferred_size(len(data))
        self.buffer = self.buffer[capacity:]
        for t in self.outputs:
            t.add_to_buffer(data)

    def run(self):
        asyncore.loop(timeout=None, use_poll=True)
        self.bw.finish()

def base64version():
    import base64
    try:
        path = __file__
    except NameError:
        # We are executing from the python command line, no file
        return
    if path.endswith('.pyc'):
        # Read from the .py source file
        path = path[:-1]
    source_lines = []
    for line in file(path):
        hash_pos = line.find(chr(35))
        if hash_pos is not -1:
            line = line[:hash_pos]
        line = line.rstrip()
        if line:
            source_lines.append(line)
    python_source = '\n'.join(source_lines)
    encoded = base64.encodestring(python_source).rstrip('\n')
    encoded = encoded.replace('\n', ',')
    return encoded

ENCODED = base64version()

def init_listening_socket(gsh_prefix):
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.bind(('', 0))
    s.listen(5)
    host = socket.gethostname()
    port = s.getsockname()[1]
    prefix = ''.join(gsh_prefix)
    if prefix:
        prefix += ' '
    print '%s%s:%s' % (prefix, host, port)
    return s

def get_destination_socket():
    fd = sys.stdin.fileno()
    old_settings = termios.tcgetattr(fd)
    new_settings = termios.tcgetattr(fd)
    new_settings[3] = new_settings[3] & ~termios.ICANON # lflags
    new_settings[6][6] = '\000' # Set VMIN to zero for lookahead only
    termios.tcsetattr(fd, termios.TCSADRAIN, new_settings)
    line = ''
    while True:
        c = os.read(sys.stdin.fileno(), 1)
        if c == '\n':
            break
        line += c
    termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)
    splitted = line.split(':', 1)
    host = splitted[0]
    port = int(splitted[1])
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.connect((host, port))
    return s

def shell_quote(s):
    return "'" + s.replace("'", "'\\''") + "'"

def silently_close_all(files):
    for f in files:
        try:
            f.close()
        except IOError:
            pass

def do_send(nr_peers, path):
    dirname, basename = os.path.split(path.rstrip('/'))
    if dirname:
        os.chdir(dirname)
    if not basename:
        basename = '/'
    stdout, stdin = popen2.popen2('tar c %s' % shell_quote(basename))
    stdin.close()
    fd = stdout.fileno()
    destination_socket = get_destination_socket()
    forw = Forwarder(nr_peers, fd, [destination_socket.fileno()])
    forw.run()
    silently_close_all([stdout, destination_socket])

def do_forward(nr_peers, gsh_prefix):
    listening_socket = init_listening_socket(gsh_prefix)
    stdout, stdin = popen2.popen2('tar x')
    stdout.close()
    fd = stdin.fileno()
    conn, addr = listening_socket.accept()
    destination_socket = get_destination_socket()
    forw = Forwarder(nr_peers, conn.fileno(), [destination_socket.fileno(), fd])
    forw.run()
    silently_close_all([conn, destination_socket, stdin])

def do_receive(nr_peers, gsh_prefix):
    listening_socket = init_listening_socket(gsh_prefix)
    stdout, stdin = popen2.popen2('tar x')
    stdout.close()
    fd = stdin.fileno()
    conn, addr = listening_socket.accept()
    forw = Forwarder(nr_peers, conn.fileno(), [fd])
    forw.run()
    silently_close_all([conn, stdin])

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

