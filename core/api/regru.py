import aiohttp
import logging
from typing import Optional

logger = logging.getLogger(__name__)

class RegRuClient:
    """
    Клиент для работы с API REG.RU Cloud VPS
    Документация: https://developers.cloudvps.reg.ru/
    """

    def __init__(self, token: str, server_id: str):
        self.token = token
        self.server_id = server_id
        self.base_url = "https://api.cloudvps.reg.ru/v1"
        self.headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json"
        }

    async def _request(self, method: str, url: str, json_data: Optional[dict] = None) -> dict:
        """
        Выполняет HTTP запрос к API
        """
        async with aiohttp.ClientSession() as session:
            try:
                logger.debug(f"API Request: {method} {url}")
                if json_data:
                    logger.debug(f"Request body: {json_data}")

                async with session.request(
                        method,
                        url,
                        headers=self.headers,
                        json=json_data,
                        timeout=aiohttp.ClientTimeout(total=30)
                ) as response:
                    response_text = await response.text()

                    if response.status == 200:
                        data = await response.json()
                        logger.debug(f"API Response: {data}")
                        return data
                    else:
                        logger.error(f"API Error {response.status}: {response_text}")
                        return {"error": response_text, "status": response.status}

            except Exception as e:
                logger.error(f"API Request failed: {e}")
                raise

    async def get_server_info(self) -> dict:
        """
        Получает информацию о сервере (reglet)

        Returns:
            {
                "reglet": {
                    "id": 5827361,
                    "name": "Minecraft-server",
                    "status": "off" | "on" | "stopping" | "starting",
                    "ip": "95.163.227.185",
                    "memory": 12288,
                    "vcpus": 4,
                    "disk": 20,
                    "disk_usage": 0.0,
                    ...
                }
            }
        """
        url = f"{self.base_url}/reglets/{self.server_id}"
        response = await self._request("GET", url)
        return response.get("reglet", {})

    async def get_balance_info(self) -> dict:
        """
        Получает информацию о балансе

        Returns:
            {
                "balance_data": {
                    "balance": 460.43,
                    "days_left": 52,
                    "hourly_cost": 0.36721,
                    "monthly_cost": 246.77,
                    ...
                }
            }
        """
        url = f"{self.base_url}/balance_data"
        response = await self._request("GET", url)
        return response.get("balance_data", {})

    async def _execute_action(self, action_type: str) -> dict:
        """
        Выполняет действие с сервером

        Args:
            action_type: "start", "stop", "reboot"

        Returns:
            {
                "action": {
                    "id": "chain_14855457",
                    "type": "start",
                    "status": "new" | "in-progress" | "completed" | "errored",
                    "created_at": "2026-01-12 04:33:05",
                    "completed_at": null,
                    ...
                }
            }

            или при блокировке:
            {
                "code": "RESOURCE_LOCKED",
                "message": "resource locked"
            }
        """
        url = f"{self.base_url}/reglets/{self.server_id}/actions"
        json_data = {"type": action_type}

        response = await self._request("POST", url, json_data)

        # Проверка на блокировку ресурса
        if response.get("code") == "RESOURCE_LOCKED":
            logger.warning(f"Server {self.server_id} is locked")
            return {"status": "locked", "message": "resource locked"}

        return response

    async def start_server(self) -> dict:
        """
        Запускает сервер

        Returns:
            {"action": {...}} или {"status": "locked"}
        """
        logger.info(f"Starting server {self.server_id}")
        return await self._execute_action("start")

    async def stop_server(self) -> dict:
        """
        Останавливает сервер

        Returns:
            {"action": {...}} или {"status": "locked"}
        """
        logger.info(f"Stopping server {self.server_id}")
        return await self._execute_action("stop")

    async def reboot_server(self) -> dict:
        """
        Перезагружает сервер

        Returns:
            {"action": {...}} или {"status": "locked"}
        """
        logger.info(f"Rebooting server {self.server_id}")
        return await self._execute_action("reboot")

    async def get_action_status(self, action_id: str) -> dict:
        """
        Проверяет статус выполнения действия

        Args:
            action_id: ID действия (например "chain_14855435")

        Returns:
            {
                "action": {
                    "id": "chain_14855435",
                    "status": "new" | "in-progress" | "completed" | "errored",
                    "type": "StopServerUseCase",
                    "completed_at": "2026-01-12 08:37:12" | null,
                    ...
                }
            }
        """
        url = f"{self.base_url}/actions/{action_id}"
        return await self._request("GET", url)

    async def wait_for_action(self, action_id: str, timeout: int = 300, check_interval: int = 5) -> bool:
        """
        Ожидает завершения действия

        Args:
            action_id: ID действия
            timeout: максимальное время ожидания в секундах
            check_interval: интервал проверки в секундах

        Returns:
            True если действие завершено успешно, False иначе
        """
        import asyncio

        elapsed = 0
        while elapsed < timeout:
            response = await self.get_action_status(action_id)
            action = response.get("action", {})
            status = action.get("status")

            logger.debug(f"Action {action_id} status: {status}")

            if status == "completed":
                logger.info(f"Action {action_id} completed successfully")
                return True
            elif status == "errored":
                logger.error(f"Action {action_id} failed")
                return False

            await asyncio.sleep(check_interval)
            elapsed += check_interval

        logger.warning(f"Action {action_id} timed out after {timeout}s")
        return False