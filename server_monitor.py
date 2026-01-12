# server_monitor.py
import aiohttp
from ssh import execute_ssh_command
from core.config import TIMEWEB_TOKEN, MINECRAFT_SERVER_ID

class ServerMonitor:
    def __init__(self, MINECRAFT_SERVER_ID: str = MINECRAFT_SERVER_ID):
        self.MINECRAFT_SERVER_ID = MINECRAFT_SERVER_ID

    async def cloud_status(self) -> str:
        headers = {"Authorization": f"Bearer {TIMEWEB_TOKEN}"}
        url = f"https://api.timeweb.cloud/api/v1/servers/{self.MINECRAFT_SERVER_ID}"

        async with aiohttp.ClientSession() as session:
            async with session.get(url, headers=headers) as resp:
                if resp.status != 200:
                    return "unknown"
                data = await resp.json()
                return data.get("server", {}).get("status", "unknown")

    async def ssh_available(self) -> bool:
        return await execute_ssh_command("echo OK") == "OK"

    async def rcon_port_open(self) -> bool:
        """Проверяет, открыт ли RCON порт (25575)"""
        out = await execute_ssh_command("nc -z localhost 25575 && echo RCON_READY")
        return "RCON_READY" in out

    async def minecraft_ready(self) -> bool:
        """Проверяет, готов ли Minecraft сервер (проверяет порт игры и RCON)"""
        # Проверяем порт игры (25565)
        game_port = await execute_ssh_command("nc -z localhost 25565 && echo READY")
        # Проверяем RCON порт (25575)
        rcon_port = await self.rcon_port_open()
        return "READY" in game_port and rcon_port

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

