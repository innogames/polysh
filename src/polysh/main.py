import argparse
import asyncio

from polysh.connection import SSHExecutor


def get_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("host_names", nargs="+")
    parser.add_argument("--command")

    return parser.parse_args()


async def run_single_command(hosts, command):
    """Run a single command and exit"""
    executors = [SSHExecutor(host) for host in hosts]

    await asyncio.gather(*[executor.login() for executor in executors])
    await asyncio.gather(*[executor.run(command) for executor in executors])
    await asyncio.gather(*[executor.logout() for executor in executors])
    await asyncio.gather(*[executor.print() for executor in executors])


def main():
    args = get_args()

    if args.command:
        asyncio.run(run_single_command(args.host_names, args.command))


if __name__ == "__main__":
    main()
