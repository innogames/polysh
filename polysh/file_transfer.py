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

import base64
import math
import os
import pipes
import random
import subprocess
import sys
import zipimport

from polysh import callbacks
from polysh import pity
from polysh.console import console_output
from polysh import remote_dispatcher
from polysh import dispatchers

def pity_dot_py_source():
    path = pity.__file__
    if not os.path.exists(path):
      try:
        zip_importer = zipimport.zipimporter(os.path.dirname(path))
      except Exception:
        return
      return zip_importer.get_source('pity')
    if not path.endswith('.py'):
        # Read from the .py source file
        dot_py_start = path.find('.py')
        if dot_py_start >= 0:
            path = path[:dot_py_start+3]

    return open(path).read()

def base64version():
    python_lines = []
    for line in pity_dot_py_source().splitlines():
        hash_pos = line.find('#')
        if hash_pos >= 0:
            line = line[:hash_pos]
        line = line.rstrip()
        if line:
            python_lines.append(line)
    python_source = '\n'.join(python_lines)
    encoded = base64.b64encode(
        python_source.encode('utf8'))
    return encoded

def tarCreate(path):
    if path:
      path = path.rstrip('/') or '/'
    else:
      path = '.'
    dirname = pipes.quote(os.path.dirname(path) or '.')
    basename = pipes.quote(os.path.basename(path) or '/')
    return 'tar c -C %s %s' % (dirname, basename)

BASE64_PITY_PY = base64version()

CMD_PREFIX = 'python3 -c "`echo "{}"|openssl base64 -d -A`" '.format(
    BASE64_PITY_PY.decode('utf8'))

CMD_UPLOAD_EMIT = ('STTY_MODE="$(stty --save)";' +
                   'stty raw &> /dev/null;' +
                   'echo %s""%s;' +
                   CMD_PREFIX + ' %s upload %s;' +
                   'stty "$STTY_MODE"\n')
CMD_REPLICATE_EMIT = '%s | ' + CMD_PREFIX + ' %s replicate %s\n'
CMD_FORWARD = CMD_PREFIX + ' %s forward %s %s %s\n'

def tree_max_children(depth):
    return 2 + depth/2

class file_transfer_tree_node(object):
    def __init__(self,
                 parent,
                 dispatcher,
                 children_dispatchers,
                 depth,
                 should_print_bw,
                 path=None,
                 is_upload=False):
        self.parent = parent
        self.host_port = None
        self.remote_dispatcher = dispatcher
        self.children = []
        if path:
            self.path = path
        self.is_upload = is_upload
        num_children = min(len(children_dispatchers), tree_max_children(depth))
        if num_children:
            child_length = int(math.ceil(float(len(children_dispatchers)) /
                                         num_children))
            depth += 1
            for i in range(num_children):
                begin = i * child_length
                if begin >= len(children_dispatchers):
                    break
                child_dispatcher = children_dispatchers[begin]
                end = begin + child_length
                begin += 1
                child = file_transfer_tree_node(self,
                                                child_dispatcher,
                                                children_dispatchers[begin:end],
                                                depth,
                                                should_print_bw)
                self.children.append(child)
        self.should_print_bw = should_print_bw(self)
        self.try_start_pity()

    def host_port_cb(self, host_port):
        self.host_port = host_port
        self.parent.try_start_pity()

    def try_start_pity(self):
        host_ports = [child.host_port for child in self.children]
        if len(list(filter(bool, host_ports))) != len(host_ports):
            return
        host_ports = ' '.join(map(pipes.quote, host_ports))
        if self.should_print_bw:
            opt = '--print-bw'
        else:
            opt = ''
        if self.parent:
            cb = lambda host_port: self.host_port_cb(host_port)
            t1, t2 = callbacks.add('file_transfer', cb, False)
            cmd = CMD_FORWARD % (opt, t1, t2, host_ports)
        elif self.is_upload:
            def start_upload(unused):
                local_uploader(self.path, self.remote_dispatcher)
            t1, t2 = callbacks.add('upload_start', start_upload, False)
            cmd = CMD_UPLOAD_EMIT % (t1, t2, opt, host_ports)
        else:
            cmd = CMD_REPLICATE_EMIT % (tarCreate(self.path), opt, host_ports)
        self.remote_dispatcher.dispatch_command(cmd)

    def __str__(self):
        children_str = ''
        for child in self.children:
            child_str = str(child)
            for line in child_str.splitlines():
                children_str += '+--%s\n' % line
        return '%s\n%s' % (self.remote_dispatcher.display_name, children_str)


def replicate(shell, path):
    peers = [i for i in dispatchers.all_instances() if i.enabled]
    if len(peers) <= 1:
        console_output('No other remote shell to replicate files to\n')
        return

    def should_print_bw(node, already_chosen=[False]):
        if not node.children and not already_chosen[0] and not node.is_upload:
            already_chosen[0] = True
            return True
        return False

    sender_index = peers.index(shell)
    destinations = peers[:sender_index] + peers[sender_index+1:]
    tree = file_transfer_tree_node(None,
                                   shell,
                                   destinations,
                                   0,
                                   should_print_bw,
                                   path=path)


class local_uploader(remote_dispatcher.remote_dispatcher):
    def __init__(self, path_to_upload, first_destination):
        self.path_to_upload = path_to_upload
        self.trigger1, self.trigger2 = callbacks.add('upload_done',
                                                     self.upload_done,
                                                     False)
        self.first_destination = first_destination
        self.first_destination.drain_and_block_writing()
        remote_dispatcher.remote_dispatcher.__init__(self, '.')
        self.temporary = True

    def launch_ssh(self, name):
        cmd = '%s | (openssl base64; echo %s) >&%d' % (
            tarCreate(self.path_to_upload),
            pity.BASE64_TERMINATOR,
            self.first_destination.fd)
        subprocess.call(cmd, shell=True)

        os.write(1, '{}{}\n'.format(self.trigger1, self.trigger2).encode('utf8'))
        os._exit(0)  # The atexit handler would kill all remote shells

    def upload_done(self, unused):
        self.first_destination.allow_writing()


def upload(local_path):
    peers = [i for i in dispatchers.all_instances() if i.enabled]
    if not peers:
        console_output('No other remote shell to replicate files to\n')
        return

    if len(peers) == 1:
        # We wouldn't be able to show the progress indicator with only one
        # destination. We need one remote connection in blocking mode to send
        # the base64 data to. We also need one remote connection in non blocking
        # mode for polysh to display the progress indicator via the main select
        # loop.
        console_output('Uploading to only one remote shell is not supported, '
                       'use scp instead\n')
        return

    def should_print_bw(node, already_chosen=[False]):
        if not node.children and not already_chosen[0]:
            already_chosen[0] = True
            return True
        return False

    tree = file_transfer_tree_node(None,
                                   peers[0],
                                   peers[1:],
                                   0,
                                   should_print_bw,
                                   path=local_path,
                                   is_upload=True)
