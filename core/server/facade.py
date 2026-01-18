import logging
from typing import Optional
from datetime import datetime

from core.api.regru import RegRuClient
from core.domain.model.server_status import ServerStatus
from core.domain.model.server_state import ServerState
from core.domain.model.action_result import ActionResult
from core.minecraft.service import get_minecraft_status, get_server_uptime
from core.config import MINECRAFT_SERVER_SSH

logger = logging.getLogger(__name__)


class ServerFacade:
    """
    Фасад для управления сервером REG.RU Cloud
    """

    def __init__(self, api_client: RegRuClient):
        self.api = api_client

    async def status(self) -> ServerStatus:
        """
        Получает полный статус сервера (VPS + Minecraft)
        """
        try:
            # Получаем информацию о сервере
            server_data = await self.api.get_server_info()
            balance_data = await self.api.get_balance_info()

            # Маппинг состояний REG.RU -> внутренние состояния
            state_map = {
                "off": ServerState.OFF,
                "stopped": ServerState.OFF,
                "starting": ServerState.STARTING,
                "on": ServerState.BOOTING,
                "active": ServerState.BOOTING,
            }

            vps_status = server_data.get("status", "off").lower()
            vps_state = state_map.get(vps_status, ServerState.OFF)

            # Базовый статус
            status = ServerStatus(
                state=vps_state,
                ip=server_data.get("ip"),
                balance=balance_data.get("balance"),
                hour_price=balance_data.get("hourly_cost"),
                uptime=None
            )

            # Если VPS не работает - возвращаем сразу
            if vps_state != ServerState.BOOTING:
                return status
            
            # Получаем uptime через SSH
            uptime = await get_server_uptime(MINECRAFT_SERVER_SSH)
            if uptime:
                status.uptime = uptime

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

            # Проверка на блокировку
            if result.get("status") == "locked":
                return ActionResult(
                    status="locked",
                    message="Сервер заблокирован (выполняется другая операция)"
                )

            # Проверяем, что действие создано
            action = result.get("action")
            if action:
                action_id = action.get("id")
                logger.info(f"Действие запуска создано: {action_id}")
                return ActionResult(
                    status="success",
                    message="Сервер запускается",
                    action_id=action_id
                )
            else:
                return ActionResult(
                    status="error",
                    message="Не удалось создать действие запуска"
                )

        except Exception as e:
            logger.error(f"Ошибка запуска сервера: {e}")
            return ActionResult(status="error", message=str(e))

    async def stop(self) -> ActionResult:
        """Останавливает VPS сервер"""
        try:
            logger.info("Остановка VPS сервера")
            result = await self.api.stop_server()

            if result.get("status") == "locked":
                return ActionResult(
                    status="locked",
                    message="Сервер заблокирован (выполняется другая операция)"
                )

            action = result.get("action")
            if action:
                action_id = action.get("id")
                logger.info(f"Действие остановки создано: {action_id}")
                return ActionResult(
                    status="success",
                    message="Сервер останавливается",
                    action_id=action_id
                )
            else:
                return ActionResult(
                    status="error",
                    message="Не удалось создать действие остановки"
                )

        except Exception as e:
            logger.error(f"Ошибка остановки сервера: {e}")
            return ActionResult(status="error", message=str(e))

    async def reboot(self) -> ActionResult:
        """Перезагружает VPS сервер"""
        try:
            logger.info("Перезагрузка VPS сервера")
            result = await self.api.reboot_server()

            if result.get("status") == "locked":
                return ActionResult(
                    status="locked",
                    message="Сервер заблокирован (выполняется другая операция)"
                )

            action = result.get("action")
            if action:
                action_id = action.get("id")
                logger.info(f"Действие перезагрузки создано: {action_id}")
                return ActionResult(
                    status="success",
                    message="Сервер перезагружается",
                    action_id=action_id
                )
            else:
                return ActionResult(
                    status="error",
                    message="Не удалось создать действие перезагрузки"
                )

        except Exception as e:
            logger.error(f"Ошибка перезагрузки сервера: {e}")
            return ActionResult(status="error", message=str(e))