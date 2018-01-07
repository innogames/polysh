[![Build Status](https://travis-ci.org/innogames/polysh.svg?branch=master)](https://travis-ci.org/innogames/polysh)

# Polysh

Polysh (formerly called Group Shell or gsh) is a remote shell multiplexor. It
lets you control many remote shells at once in a single shell. Unlike other
commands dispatchers, it is interactive, so shells spawned on the remote hosts
are persistent. It requires only a SSH server on the remote hosts, or some other
way to open a remote shell.

# Requirements

Python >= 3.something is required.

# Running

You can run polysh without installing it simply by executing the polysh.py file
in the toplevel directory.

# Installation

Polysh uses the distutils, so the command './setup.py install' will install it
in the default python directory. It should also install the polysh script in
/usr/local/bin.



--
Guillaume Chazarain <guichaz@gmail.com>
http://guichaz.free.fr/polysh
