#!/usr/bin/env python3
"""Benchmark script for comparing polysh event loop implementations.

Compares the old asyncore-based event loop (master branch) against the new
selectors-based event loop (g_asyncio branch) by running polysh in
non-interactive mode and measuring wall-clock time.

Usage examples:
    # Compare two binaries with explicit server list
    ./benchmark.py --binary-old ./result-old/bin/polysh \
                   --binary-new ./result-new/bin/polysh \
                   server1 server2 server3

    # Single binary benchmark (just timing, no comparison)
    ./benchmark.py --binary ./result/bin/polysh server1 server2

    # Use adminapi to resolve servers
    ./benchmark.py --binary-old ./result-old/bin/polysh \
                   --binary-new ./result-new/bin/polysh \
                   --adminapi 'project=grepo game_market=xx servertype=vm'

    # Custom command and more runs
    ./benchmark.py --binary-old ./result-old/bin/polysh \
                   --binary-new ./result-new/bin/polysh \
                   --command 'cat /proc/loadavg' \
                   --runs 10 \
                   server1 server2

    # With custom ssh command
    ./benchmark.py --binary ./result/bin/polysh \
                   --ssh 'exec ssh -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null -oLogLevel=Quiet -t %(host)s %(port)s' \
                   server1 server2
"""

import argparse
import json
import math
import os
import resource
import shutil
import subprocess
import sys
import time


def resolve_adminapi(query):
    """Resolve server names using adminapi CLI tool."""
    try:
        result = subprocess.run(
            ['adminapi', query],
            capture_output=True,
            text=True,
            timeout=30,
        )
        if result.returncode != 0:
            print(f'adminapi failed: {result.stderr.strip()}', file=sys.stderr)
            sys.exit(1)
        servers = result.stdout.strip().split()
        if not servers:
            print('adminapi returned no servers', file=sys.stderr)
            sys.exit(1)
        return servers
    except FileNotFoundError:
        print('adminapi not found in PATH', file=sys.stderr)
        sys.exit(1)


def build_polysh_cmd(binary, ssh_cmd, command, servers):
    """Build the polysh command line."""
    cmd = [binary]
    if ssh_cmd:
        cmd.extend(['--ssh', ssh_cmd])
    cmd.extend(['--command', command])
    cmd.extend(servers)
    return cmd


def run_single(cmd, run_number, quiet=False):
    """Run a single polysh invocation and return wall-clock time in seconds."""
    if not quiet:
        print(f'  Run {run_number}... ', end='', flush=True)

    start = time.monotonic()
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            timeout=300,  # 5 minute timeout per run
        )
    except subprocess.TimeoutExpired:
        if not quiet:
            print('TIMEOUT')
        return None

    elapsed = time.monotonic() - start

    if not quiet:
        if result.returncode != 0:
            print(f'{elapsed:.3f}s (exit code {result.returncode})')
        else:
            print(f'{elapsed:.3f}s')

    return elapsed


def run_benchmark(label, cmd, runs, warmup):
    """Run multiple iterations of a benchmark and collect timings."""
    print(f'\n--- {label} ---')
    print(f'Command: {" ".join(cmd)}')
    print(f'Warmup runs: {warmup}, Measured runs: {runs}')

    # Warmup
    for i in range(warmup):
        print(f'  Warmup {i + 1}... ', end='', flush=True)
        t = run_single(cmd, i + 1, quiet=True)
        if t is not None:
            print(f'{t:.3f}s')
        else:
            print('TIMEOUT')

    # Measured runs
    timings = []
    for i in range(runs):
        t = run_single(cmd, i + 1)
        if t is not None:
            timings.append(t)

    return timings


def compute_stats(timings):
    """Compute basic statistics from a list of timings."""
    if not timings:
        return None

    n = len(timings)
    mean = sum(timings) / n
    sorted_t = sorted(timings)
    median = sorted_t[n // 2] if n % 2 else (sorted_t[n // 2 - 1] + sorted_t[n // 2]) / 2

    if n > 1:
        variance = sum((t - mean) ** 2 for t in timings) / (n - 1)
        stddev = math.sqrt(variance)
    else:
        stddev = 0.0

    return {
        'n': n,
        'mean': mean,
        'median': median,
        'min': sorted_t[0],
        'max': sorted_t[-1],
        'stddev': stddev,
    }


def print_stats(label, stats):
    """Print statistics for a benchmark run."""
    if stats is None:
        print(f'\n{label}: No successful runs')
        return

    print(f'\n{label} ({stats["n"]} runs):')
    print(f'  Mean:   {stats["mean"]:.3f}s')
    print(f'  Median: {stats["median"]:.3f}s')
    print(f'  Min:    {stats["min"]:.3f}s')
    print(f'  Max:    {stats["max"]:.3f}s')
    print(f'  Stddev: {stats["stddev"]:.3f}s')


def print_comparison(stats_old, stats_new):
    """Print comparison between old and new implementations."""
    if stats_old is None or stats_new is None:
        print('\nCannot compare: one or both benchmarks had no successful runs')
        return

    diff = stats_new['mean'] - stats_old['mean']
    if stats_old['mean'] > 0:
        pct = (diff / stats_old['mean']) * 100
    else:
        pct = 0.0

    print('\n=== Comparison ===')
    print(f'  Old mean: {stats_old["mean"]:.3f}s')
    print(f'  New mean: {stats_new["mean"]:.3f}s')
    print(f'  Diff:     {diff:+.3f}s ({pct:+.1f}%)')

    if diff < 0:
        print(f'  New is {abs(pct):.1f}% faster')
    elif diff > 0:
        print(f'  New is {pct:.1f}% slower')
    else:
        print('  No difference')

    # Also compare medians
    diff_med = stats_new['median'] - stats_old['median']
    if stats_old['median'] > 0:
        pct_med = (diff_med / stats_old['median']) * 100
    else:
        pct_med = 0.0
    print(f'  Median diff: {diff_med:+.3f}s ({pct_med:+.1f}%)')


def main():
    parser = argparse.ArgumentParser(
        description='Benchmark polysh event loop implementations',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )

    # Binary selection - mutually exclusive groups
    binary_group = parser.add_mutually_exclusive_group(required=True)
    binary_group.add_argument(
        '--binary',
        help='Single polysh binary to benchmark (timing only, no comparison)',
    )
    binary_group.add_argument(
        '--binary-old',
        help='Path to old (asyncore) polysh binary',
    )

    parser.add_argument(
        '--binary-new',
        help='Path to new (selectors) polysh binary (required with --binary-old)',
    )

    # Server selection
    parser.add_argument(
        'servers',
        nargs='*',
        help='Server hostnames to connect to',
    )
    parser.add_argument(
        '--adminapi',
        help='adminapi query string to resolve server names',
    )

    # Polysh options
    parser.add_argument(
        '--ssh',
        default='exec ssh -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null -oLogLevel=Quiet -t %(host)s %(port)s',
        help='SSH command template (default: %(default)s)',
    )
    parser.add_argument(
        '--command',
        default='hostname',
        help='Command to execute on remote hosts (default: %(default)s)',
    )

    # Benchmark parameters
    parser.add_argument(
        '--runs',
        type=int,
        default=5,
        help='Number of measured runs (default: %(default)s)',
    )
    parser.add_argument(
        '--warmup',
        type=int,
        default=1,
        help='Number of warmup runs (default: %(default)s)',
    )
    parser.add_argument(
        '--json',
        metavar='FILE',
        help='Write results as JSON to FILE',
    )

    args = parser.parse_args()

    # Validate binary arguments
    if args.binary_old and not args.binary_new:
        parser.error('--binary-new is required when using --binary-old')

    # Resolve servers
    servers = list(args.servers) if args.servers else []
    if args.adminapi:
        servers.extend(resolve_adminapi(args.adminapi))
    if not servers:
        parser.error('No servers specified. Use positional args or --adminapi')

    # Validate binaries exist
    binaries = {}
    if args.binary:
        if not os.path.isfile(args.binary) or not os.access(args.binary, os.X_OK):
            print(f'Binary not found or not executable: {args.binary}', file=sys.stderr)
            sys.exit(1)
        binaries['single'] = args.binary
    else:
        for label, path in [('old', args.binary_old), ('new', args.binary_new)]:
            if not os.path.isfile(path) or not os.access(path, os.X_OK):
                print(f'Binary not found or not executable: {path}', file=sys.stderr)
                sys.exit(1)
            binaries[label] = path

    print(f'Servers ({len(servers)}): {" ".join(servers[:10])}{"..." if len(servers) > 10 else ""}')
    print(f'Command: {args.command}')
    print(f'SSH: {args.ssh}')
    print(f'Runs: {args.runs} (+ {args.warmup} warmup)')

    results = {}

    if 'single' in binaries:
        cmd = build_polysh_cmd(binaries['single'], args.ssh, args.command, servers)
        timings = run_benchmark('Polysh', cmd, args.runs, args.warmup)
        stats = compute_stats(timings)
        print_stats('Polysh', stats)
        results['single'] = {'timings': timings, 'stats': stats}
    else:
        # Run old first, then new
        cmd_old = build_polysh_cmd(binaries['old'], args.ssh, args.command, servers)
        timings_old = run_benchmark('Old (asyncore)', cmd_old, args.runs, args.warmup)
        stats_old = compute_stats(timings_old)

        cmd_new = build_polysh_cmd(binaries['new'], args.ssh, args.command, servers)
        timings_new = run_benchmark('New (selectors)', cmd_new, args.runs, args.warmup)
        stats_new = compute_stats(timings_new)

        print_stats('Old (asyncore)', stats_old)
        print_stats('New (selectors)', stats_new)
        print_comparison(stats_old, stats_new)

        results['old'] = {'timings': timings_old, 'stats': stats_old}
        results['new'] = {'timings': timings_new, 'stats': stats_new}

    # Write JSON output if requested
    if args.json:
        json_data = {
            'servers': servers,
            'command': args.command,
            'ssh': args.ssh,
            'runs': args.runs,
            'warmup': args.warmup,
            'results': results,
        }
        with open(args.json, 'w') as f:
            json.dump(json_data, f, indent=2)
        print(f'\nJSON results written to {args.json}')


if __name__ == '__main__':
    main()
