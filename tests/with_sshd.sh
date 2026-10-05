#!/bin/sh
# Run the test suite through a real ssh transport: start a private sshd as
# the current user on a free port of 127.0.0.1, point the tests at it with
# POLYSH_TEST_SSH (see tests/__init__.py) and run the command given as
# arguments, by default the whole suite.  Needs the openssh-server package,
# nothing else configured, no root.
#
#     tests/with_sshd.sh
#     tests/with_sshd.sh uv run python -m unittest -v tests.test_basic
set -eu

sshd=$(command -v sshd || echo /usr/sbin/sshd)
if [ ! -x "$sshd" ]; then
    echo "sshd not found, install the openssh-server package" >&2
    exit 1
fi

dir=$(mktemp -d)
sshd_pid=
cleanup() {
    [ -n "$sshd_pid" ] && kill "$sshd_pid" 2>/dev/null
    rm -rf "$dir"
}
trap cleanup EXIT INT TERM

ssh-keygen -q -t ed25519 -N '' -f "$dir/host_key"
ssh-keygen -q -t ed25519 -N '' -f "$dir/user_key"
cp "$dir/user_key.pub" "$dir/authorized_keys"
port=$(python3 -c 'import socket
s = socket.socket()
s.bind(("127.0.0.1", 0))
print(s.getsockname()[1])')

cat > "$dir/sshd_config" <<CONF
Port $port
ListenAddress 127.0.0.1
HostKey $dir/host_key
AuthorizedKeysFile $dir/authorized_keys
PasswordAuthentication no
KbdInteractiveAuthentication no
UsePAM no
StrictModes no
PidFile none
PrintMotd no
PrintLastLog no
# The same bare login bash as tests/fake_ssh.sh, whatever the login shell
# and profile files of the user running the tests
ForceCommand bash --noprofile --norc -l
CONF

"$sshd" -D -f "$dir/sshd_config" -E "$dir/sshd.log" &
sshd_pid=$!

# LogLevel ERROR rather than polysh's default Quiet, so that a refused key
# or a dying session shows up in the test output
ssh_options="-p $port -i $dir/user_key -o StrictHostKeyChecking=no \
-o UserKnownHostsFile=/dev/null -o IdentitiesOnly=yes -o LogLevel=ERROR"
tries=0
# -n: with ForceCommand the probe runs that bash, which leaves on EOF
# shellcheck disable=SC2086
until ssh $ssh_options -o BatchMode=yes -n localhost 2>/dev/null; do
    tries=$((tries + 1))
    if [ "$tries" -ge 50 ]; then
        echo "sshd did not come up on port $port:" >&2
        cat "$dir/sshd.log" >&2
        exit 1
    fi
    sleep 0.2
done

POLYSH_TEST_SSH="exec ssh $ssh_options -t %(host)s"
export POLYSH_TEST_SSH
if [ $# -eq 0 ]; then
    set -- uv run python -m unittest discover -v tests
fi
"$@"
