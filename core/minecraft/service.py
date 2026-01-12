# minecraft/service.py
import re

from core.ssh.client import run, is_available

async def is_ready() -> bool:
    return "READY" in await run("nc -z localhost 25565 && echo READY")


async def players_count() -> int:
    output = await run("/root/scripts/players.sh")

    if not output or "❌" in output:
        return -1

    match = re.search(r"There are (\d+) of a max", output)
    if match:
        return int(match.group(1))

    if "There are 0" in output:
        return 0

    return -1


async def stop() -> str:
    return await run("/root/scripts/stop_server_manually.sh")


async def reboot() -> str:
    return await run("/root/scripts/reboot_server_manually.sh")
