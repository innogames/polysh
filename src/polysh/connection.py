import asyncio
import typing


class SSHExecutor:
    def __init__(self, host: str):
        self.host: typing.Optional[str] = host
        self.process: typing.Optional[asyncio.subprocess.Process] = None
        self.stdin: typing.Optional[asyncio.streams.StreamWriter] = None
        self.stdout: typing.Optional[asyncio.streams.StreamReader] = None

    async def login(self):
        self.process = await asyncio.create_subprocess_exec(
            "/bin/ssh",
            *[
                "-tt",  # Force pseudo-terminal allocation
                self.host,
                "/bin/sh", # Start Shell
            ],
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.STDOUT  # Redirect stderr to stdout
        )

        # For convenience
        self.stdin = self.process.stdin
        self.stdout = self.process.stdout

    async def run(self, command: str):
        # Ensure newline is present otherwise the command is not submitted
        command = command if command.endswith("\n") else f"{command}\n"

        # TODO: Check if awaiting drain is sufficient to prevent deadlocks
        #
        # Warning Use the communicate() method rather than process.stdin.write(),
        # await process.stdout.read() or await process.stderr.read().
        # This avoids deadlocks due to streams pausing reading or writing and blocking the child process.
        #
        # Source: https://docs.python.org/3/library/asyncio-subprocess.html
        self.stdin.write(command.encode())
        await self.stdin.drain()

    async def logout(self):
        await self.run("exit $?")

    async def print(self):
        while True:
            if self.stdout.at_eof():
                break

            output = (await self.stdout.readline()).decode()
            # Ensure each line we print has the hostname as prefix
            formatted_output = "\r".join([f"{self.host} : {part}" for part in output.split("\r")])
            print(formatted_output, end="")