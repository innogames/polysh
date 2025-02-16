import argparse
import asyncio

from polysh.connection import SSHExecutor


def get_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("host_names", nargs="+")
    parser.add_argument("--command")

    return parser.parse_args()


async def run(hosts, command):
    executors = [SSHExecutor(host) for host in hosts]

    await asyncio.gather(*[executor.connect() for executor in executors])
    for executor in executors:
        await executor.run_command(command)
        print(executor.stdout.decode())


def main():
    args = get_args()
    asyncio.run(run(args.host_names, args.command))


if __name__ == "__main__":
    main()
