# test_monitoring.py
import asyncio
import logging
from core.server.facade import ServerFacade
from core.api.regru import RegRuClient
from core.config import REGRU_CLOUD_TOKEN, MINECRAFT_SERVER_ID
from core.domain.model.server_state import ServerState

logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)


async def test():
    reg_ru_api = RegRuClient(REGRU_CLOUD_TOKEN, MINECRAFT_SERVER_ID)
    facade = ServerFacade(reg_ru_api)

    print("🧪 Тест получения статуса для мониторинга\n")

    for i in range(5):
        print(f"\n=== Попытка {i + 1} ===")
        status = await facade.status()

        print(f"State: {status.state}")
        print(f"Players: {status.players}/{status.max_players}")
        print(f"Ready: {status.state == ServerState.READY}")

        await asyncio.sleep(10)


if __name__ == "__main__":
    asyncio.run(test())