import aiohttp
from typing import Optional
import logging

# Настройка логирования
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

class RegRuClient:
    BASE_URL = "https://api.cloudvps.reg.ru/v1"

    def __init__(self, token: str, reglet_id: int):
        self.token = token
        self.reglet_id = reglet_id

    # ---------- low-level ----------

    @property
    def headers(self) -> dict:
        return {
            "Authorization": f"Bearer {self.token}",
            "Content-Type": "application/json",
        }

    async def _post_action(self, action_type: str) -> dict:
        """
        start / stop / reboot
        """
        url = f"{self.BASE_URL}/reglets/{self.reglet_id}/actions"
        payload = {"type": action_type}

        async with aiohttp.ClientSession() as session:
            async with session.post(url, headers=self.headers, json=payload) as resp:
                data = await resp.json()

                if resp.status == 409:
                    # RESOURCE_LOCKED
                    return {
                        "status": "locked",
                        "raw": data,
                    }

                resp.raise_for_status()
                return data

    async def _get_action(self, action_id: str) -> dict:
        url = f"{self.BASE_URL}/actions/{action_id}"

        async with aiohttp.ClientSession() as session:
            async with session.get(url, headers=self.headers) as resp:
                resp.raise_for_status()
                return await resp.json()

    # ---------- public: actions ----------

    async def start(self) -> Optional[str]:
        return await self._run_action("start")

    async def stop(self) -> Optional[str]:
        return await self._run_action("stop")

    async def reboot(self) -> Optional[str]:
        return await self._run_action("reboot")

    async def _run_action(self, action_type: str) -> Optional[str]:
        """
        Returns action_id or None if locked
        """
        result = await self._post_action(action_type)

        if result.get("status") == "locked":
            return None

        return result["action"]["id"]

    async def get_action_status(self, action_id: str) -> str:
        """
        new | in-progress | errored | completed
        """
        data = await self._get_action(action_id)
        return data["action"]["status"]

    # ---------- public: server info ----------

    async def get_server_info(self) -> dict:
        url = f"{self.BASE_URL}/reglets/{self.reglet_id}"

        async with aiohttp.ClientSession() as session:
            async with session.get(url, headers=self.headers) as resp:
                resp.raise_for_status()
                return await resp.json()

    async def get_server_state(self) -> str:
        """
        on / off
        """
        info = await self.get_server_info()
        return info["reglet"]["status"]

    # ---------- billing ----------

    async def get_balance(self) -> dict:
        url = f"{self.BASE_URL}/balance_data"

        async with aiohttp.ClientSession() as session:
            async with session.get(url, headers=self.headers) as resp:
                resp.raise_for_status()
                return await resp.json()
