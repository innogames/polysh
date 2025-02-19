import asyncio


class SSHExecutor:
    def __init__(self, host: str):
        self.host = host
        self.process = None
        self.stdout = None
        self.stderr = None

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
            stderr=asyncio.subprocess.PIPE
        )

        self.stdout = self.process.stdout
        self.stderr = self.process.stderr

    async def run(self, command):
        # Ensure newline is present otherwise the command is not submitted
        command = command if command.endswith("\n") else f"{command}\n"

        # TODO: Check if awaiting drain is sufficient to prevent deadlocks
        #
        # Warning Use the communicate() method rather than process.stdin.write(),
        # await process.stdout.read() or await process.stderr.read().
        # This avoids deadlocks due to streams pausing reading or writing and blocking the child process.
        #
        # Source: https://docs.python.org/3/library/asyncio-subprocess.html
        self.process.stdin.write(command.encode())
        await self.process.stdin.drain()

    async def logout(self):
        await self.run("exit $?")