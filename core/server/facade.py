# core/server/facade.py
import asyncio
import logging

from core.domain.model.action_result import ActionResult
from core.domain.model.server_status import ServerStatus
from core.domain.model.server_state import ServerState
from core.minecraft.service import is_ready, players_count, players_with_names_count
from core.ssh.client import is_available
from core.minecraft.service import (
    is_ready,
    players_count,
    save_and_stop,
    save_and_prepare_reboot
)
from core.ssh.client import is_available
from core.api.regru import RegRuClient

logger = logging.getLogger(__name__)

class ServerFacade:
    def __init__(self, regru: RegRuClient):
        self.regru = regru
        self._lock = asyncio.Lock()

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
        # Проверяем блокировку
        if self._lock.locked():
            logger.warning("Операция stop заблокирована - уже выполняется другая операция")
            return ActionResult(None, "locked")

        async with self._lock:
            try:
                logger.info("Начало процедуры остановки сервера")

                # Сохраняем и останавливаем Minecraft
                if await is_available():
                    logger.info("Minecraft доступен, сохраняю мир...")
                    await save_and_stop()
                else:
                    logger.info("Minecraft не доступен, пропускаю сохранение")

                # Выключаем VPS через API
                logger.info("Отправляю команду на отключение VPS...")
                action_id = await self.regru.stop()

                if not action_id:
                    logger.error("Не удалось получить action_id от API")
                    return ActionResult(None, "locked")

                logger.info(f"VPS отключение запущено, action_id: {action_id}")
                return ActionResult(action_id, "new")

            except Exception as e:
                logger.error(f"Ошибка при остановке сервера: {e}")
                return ActionResult(None, "error", str(e))

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
        vps_balance = await self.regru.get_balance_string()
        print(vps_state)
        # VPS выключен
        if vps_state == "off":
            return ServerStatus(state=ServerState.OFF)

        # VPS включается (action new / in-progress)
        if vps_state in {"new", "in-progress", "starting"}:
            return ServerStatus(state=ServerState.STARTING)

        # VPS включен
        if vps_state == "active":

            # VPS есть, SSH есть → проверяем Minecraft
            if await is_ready():
                players, max_players, names = await players_with_names_count()
                print(f"players: {players}")
                info = await self.regru.get_server_info()

                return ServerStatus(
                    state=ServerState.READY,
                    players=players,
                    max_players=max_players,
                    names=names,
                    ip=info["reglet"]["ip"],
                    ram = info["reglet"]["memory"],
                    disk = f"{info['reglet']['image']['size_gigabytes']} / {info['reglet']['disk']}",
                    balance=vps_balance
                )

            return ServerStatus(state=ServerState.BOOTING)

        return ServerStatus(state=ServerState.ERROR)