# server/facade.py
from core.domain.model.action_result import ActionResult
from core.domain.model.server_status import ServerStatus
from core.domain.model.server_state import ServerState
from core.minecraft.service import is_ready, players_count
from core.ssh.client import is_available
from core.minecraft.service import (
    is_ready,
    players_count,
    save_and_stop,
    save_and_prepare_reboot
)
from core.ssh.client import is_available
from core.api.regru import RegRuClient

class ServerFacade:
    def __init__(self, regru: RegRuClient):
        self.regru = regru

    # ---------- HIGH LEVEL ----------

    async def start(self) -> ActionResult:
        """
        Запуск = включение VPS через API
        Minecraft поднимется systemd-ом
        """
        action_id = await self.regru.start()
        if not action_id:
            return ActionResult(None, "locked")

        return ActionResult(action_id, "new")

    async def stop(self) -> ActionResult:
        """
        1. Корректно остановить Minecraft (scripts)
        2. Выключить VPS через API
        """
        if await is_available():
            await save_and_stop()

        action_id = await self.regru.stop()
        if not action_id:
            return ActionResult(None, "locked")

        return ActionResult(action_id, "new")

    async def reboot(self) -> ActionResult:
        """
        1. Корректно остановить Minecraft
        2. Reboot VPS через API
        """
        if await is_available():
            await save_and_prepare_reboot()

        action_id = await self.regru.reboot()
        if not action_id:
            return ActionResult(None, "locked")

        return ActionResult(action_id, "new")

    # ---------- STATUS ----------

    async def status(self) -> ServerStatus:
        vps_state = await self.regru.get_server_state()

        # VPS выключен
        if vps_state == "off":
            return ServerStatus(state=ServerState.OFF)

        # VPS включается (action new / in-progress)
        if vps_state in {"new", "in-progress", "starting"}:
            return ServerStatus(state=ServerState.STARTING)

        # VPS включен
        if vps_state == "on":
            if not await is_available():
                return ServerStatus(state=ServerState.STARTING)

            # VPS есть, SSH есть → проверяем Minecraft
            if await is_ready():
                players = await players_count()
                info = await self.regru.get_server_info()

                return ServerStatus(
                    state=ServerState.READY,
                    players=players,
                    ip=info["reglet"]["ip"],
                )

            return ServerStatus(state=ServerState.BOOTING)

        return ServerStatus(state=ServerState.ERROR)