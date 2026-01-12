# ssh/client.py
import asyncio
import logging

from core.config import MINECRAFT_SERVER_SSH

logger = logging.getLogger(__name__)


async def run(command: str, timeout: int = 20) -> str:
    try:
        proc = await asyncio.create_subprocess_shell(
            f"ssh -o ConnectTimeout=10 -o StrictHostKeyChecking=no "
            f"{MINECRAFT_SERVER_SSH} '{command}'",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )

        stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout)

        if proc.returncode == 0:
            return stdout.decode().strip()

        return f"❌ SSH error: {stderr.decode().strip()}"

    except asyncio.TimeoutError:
        return "❌ SSH timeout"
    except Exception as e:
        return f"❌ SSH exception: {e}"


async def is_available() -> bool:
    return "SSH_OK" in await run("echo SSH_OK")
