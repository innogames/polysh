#!/bin/sh
# Stand-in for ssh in the test suite, see tests/conftest.py.
#
# The local host, by any of its names, gets a local login shell: a login
# shell prints "logout" on exit, as the one ssh would start does and as the
# tests expect.  Any other host fails the way ssh fails on an unknown host.
case "$1" in
    localhost|127.0.0.1|::1)
        exec bash --noprofile --norc -l
        ;;
    *)
        echo "ssh: Could not resolve hostname $1: Name or service not known" >&2
        exit 255
        ;;
esac
