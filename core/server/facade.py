import logging
from typing import Optional
from datetime import datetime

from core.api.regru import RegRuClient
from core.domain.model.server_status import ServerStatus
from core.domain.model.server_state import ServerState
from core.domain.model.action_result import ActionResult
from core.minecraft.service import get_minecraft_status
from core.config import MINECRAFT_SERVER_SSH

logger = logging.getLogger(__name__)


class ServerFacade:
    """
    Фасад для управления сервером.
    Объединяет работу с VPS API и Minecraft сервером.
    """

    def __init__(self, api_client: RegRuClient):
        self.api = api_client
        self._status_cache: Optional[ServerStatus] = None
        self._cache_time: Optional[datetime] = None
        self._cache_ttl = 10  # секунд

    async def status(self) -> ServerStatus:
        """
        Получает полный статус сервера (VPS + Minecraft)
        """
        try:
            # Получаем статус VPS
            vps_data = await self.api.get_server_info()

            state_map = {
                "off": ServerState.OFF,
                "starting": ServerState.STARTING,
                "on": ServerState.BOOTING,
            }

            vps_state = state_map.get(vps_data.get("state", "off"), ServerState.OFF)

            # Базовый статус
            status = ServerStatus(
                state=vps_state,
                ip=vps_data.get("main_ipv4"),
                uptime=vps_data.get("uptime")
            )

            # Если VPS не работает - возвращаем сразу
            if vps_state != ServerState.BOOTING:
                return status

            # Проверяем Minecraft
            mc_status = await get_minecraft_status(MINECRAFT_SERVER_SSH)

            if mc_status['active']:
                status.state = ServerState.READY
                status.minecraft_active = True
                status.players = mc_status['players']
                status.max_players = mc_status['max_players']
                status.names = mc_status['names']

            logger.debug(f"Status: {status.state}, Players: {status.players}/{status.max_players}")
            return status

        except Exception as e:
            logger.error(f"Ошибка получения статуса сервера: {e}")
            return ServerStatus(state=ServerState.OFF)

    async def start(self) -> ActionResult:
        """Запускает VPS сервер"""
        try:
            logger.info("Запуск VPS сервера")
            result = await self.api.start_server()

            if result.get("state") == "starting":
                return ActionResult(status="success", message="Сервер запускается")
            elif result.get("state") == "on":
                return ActionResult(status="success", message="Сервер уже запущен")
            else:
                return ActionResult(status="locked", message="Сервер выполняет другую операцию")

        except Exception as e:
            logger.error(f"Ошибка запуска сервера: {e}")
            return ActionResult(status="error", message=str(e))

    async def stop(self) -> ActionResult:
        """Останавливает VPS сервер (с сохранением мира Minecraft)"""
        try:
            logger.info("Остановка VPS сервера")

            # Проверяем, запущен ли Minecraft
            status = await self.status()

            if status.state == ServerState.READY and status.minecraft_active:
                logger.info("Выполняю save-all перед остановкой")
                # Сохранение происходит автоматически через systemd ExecStop

            result = await self.api.stop_server()

            if result.get("state") == "stopping" or result.get("state") == "off":
                return ActionResult(status="success", message="Сервер останавливается")
            else:
                return ActionResult(status="locked", message="Сервер выполняет другую операцию")

        except Exception as e:
            logger.error(f"Ошибка остановки сервера: {e}")
            return ActionResult(status="error", message=str(e))

    async def reboot(self) -> ActionResult:
        """Перезагружает VPS сервер"""
        try:
            logger.info("Перезагрузка VPS сервера")
            result = await self.api.reboot_server()

            if result.get("state") in ["rebooting", "starting"]:
                return ActionResult(status="success", message="Сервер перезагружается")
            else:
                return ActionResult(status="locked", message="Сервер выполняет другую операцию")

        except Exception as e:
            logger.error(f"Ошибка перезагрузки сервера: {e}")
            return ActionResult(status="error", message=str(e))