# server_monitor.py
import aiohttp
from ssh import execute_ssh_command
from config import TIMEWEB_TOKEN, SERVER_ID

class ServerMonitor:
    def __init__(self, server_id: str = SERVER_ID):
        self.server_id = server_id

    async def cloud_status(self) -> str:
        headers = {"Authorization": f"Bearer {TIMEWEB_TOKEN}"}
        url = f"https://api.timeweb.cloud/api/v1/servers/{self.server_id}"

        async with aiohttp.ClientSession() as session:
            async with session.get(url, headers=headers) as resp:
                if resp.status != 200:
                    return "unknown"
                data = await resp.json()
                return data.get("server", {}).get("status", "unknown")

    async def ssh_available(self) -> bool:
        return await execute_ssh_command("echo OK") == "OK"

    async def minecraft_ready(self) -> bool:
        out = await execute_ssh_command("nc -z localhost 25565 && echo READY")
        return "READY" in out

    async def players(self) -> str:
        return await execute_ssh_command("/root/scripts/players.sh")

    async def full_status(self) -> str:
        cloud = await self.cloud_status()
        ssh = await self.ssh_available()
        mc = False

        if ssh:
            mc = await self.minecraft_ready()

        status = []

        # Cloud — только справка
        if cloud == "running":
            status.append("☁️ Cloud: running")
        elif cloud:
            status.append(f"☁️ Cloud: {cloud}")
        else:
            status.append("☁️ Cloud: unknown")

        # SSH
        status.append("🖥 SSH: ✅" if ssh else "🖥 SSH: ❌")

        # Minecraft — ГЛАВНОЕ
        if mc:
            players = await self.players()
            status.append("🎮 Minecraft: ✅ PLAYABLE")
            status.append(f"👥 {players}")
        elif ssh:
            status.append("🎮 Minecraft: ⏳ (starting)")
        else:
            status.append("🎮 Minecraft: ❌")

        return "\n".join(status)

