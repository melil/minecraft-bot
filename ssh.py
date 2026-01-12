# ssh.py
import asyncio
from core.config import MINECRAFT_SERVER_SSH

async def execute_ssh_command(command: str) -> str:
    try:
        proc = await asyncio.create_subprocess_shell(
            f"ssh -o ConnectTimeout=10 -o StrictHostKeyChecking=no {MINECRAFT_SERVER_SSH} '{command}'",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )

        stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=20)

        if proc.returncode == 0:
            return stdout.decode().strip()
        else:
            return stderr.decode().strip()

    except asyncio.TimeoutError:
        return "TIMEOUT"
    except Exception as e:
        return f"ERROR: {e}"
