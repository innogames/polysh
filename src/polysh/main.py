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

    async def process(executor: SSHExecutor):
        # Ensure ordering so we e.g. do not run a command before login.
        await executor.login()
        await executor.run(command)
        await executor.logout()
        await executor.print()

    await asyncio.gather(*[process(executor) for executor in executors])

def main():
    args = get_args()

    if args.command:
        asyncio.run(run_single_command(args.host_names, args.command))


if __name__ == "__main__":
    main()
