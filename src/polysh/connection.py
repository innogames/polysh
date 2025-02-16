import asyncio


class SSHExecutor:
    def __init__(self, host: str):
        self.host = host
        self.process = None
        self.stdout = None
        self.stderr = None

    async def connect(self):
        self.process = await asyncio.create_subprocess_exec(
            "/bin/ssh",
            *[
                "-t",  # Force pseudo-terminal allocation
                self.host
            ],
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )

    async def run_command(self, command):
        self.stdout, self.stderr = await self.process.communicate(input=(command + "\n").encode())
