import asyncio

from core.api.regru import RegRuClient
from core.ssh.client import run, is_available
from core.minecraft.service import is_ready, players_count, stop as stop_mc
from core.server.models import ActionResult, ServerStatus

class ServerFacade:
    def __init__(self, regru: RegRuClient):
        self.regru = regru

    # ---------- VPS ----------

    async def start_vps(self) -> ActionResult:
        action_id = await self.regru.start()
        if not action_id:
            return ActionResult(None, "locked")

        return ActionResult(action_id, "new")

    async def stop_vps(self) -> ActionResult:
        action_id = await self.regru.stop()
        if not action_id:
            return ActionResult(None, "locked")

        return ActionResult(action_id, "new")

    async def reboot_vps(self) -> ActionResult:
        action_id = await self.regru.reboot()
        if not action_id:
            return ActionResult(None, "locked")

        return ActionResult(action_id, "new")

    async def action_status(self, action_id: str) -> str:
        return await self.regru.get_action_status(action_id)

    # ---------- Minecraft ----------

    async def minecraft_running(self) -> bool:
        if not await is_available():
            return False
        return await is_ready()

    async def stop_minecraft(self) -> str:
        return await stop_mc()

    async def players(self) -> int:
        return await players_count()

    # ---------- High level ----------

    async def start(self) -> ActionResult:
        """
        Запуск сервера = запуск VPS
        """
        return await self.start_vps()

    async def stop(self) -> ActionResult:
        """
        Корректная остановка:
        1. Остановить Minecraft
        2. Остановить VPS
        """
        await self.stop_minecraft()
        return await self.stop_vps()

    async def status(self) -> ServerStatus:
        vps_state = await self.regru.get_server_state()

        mc_active = False
        players = -1
        ip = None

        if vps_state == "on" and await is_available():
            mc_active = await is_ready()
            players = await players_count()

            info = await self.regru.get_server_info()
            ip = info["reglet"]["ip"]

        return ServerStatus(
            vps_status=vps_state,
            minecraft_active=mc_active,
            players=players,
            ip=ip
        )
