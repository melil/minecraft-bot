#!/usr/bin/env python3
import asyncio
import json
from core.api.regru import RegRuClient
from core.config import REGRU_CLOUD_TOKEN, MINECRAFT_SERVER_ID


async def main():
    print("🧪 Тест REG.RU Cloud API\n")

    client = RegRuClient(REGRU_CLOUD_TOKEN, MINECRAFT_SERVER_ID)

    # 1. Информация о сервере
    print("1️⃣ Информация о сервере:")
    server_info = await client.get_server_info()
    print(json.dumps(server_info, indent=2, ensure_ascii=False))

    # 2. Баланс
    print("\n2️⃣ Информация о балансе:")
    balance_info = await client.get_balance_info()
    print(json.dumps(balance_info, indent=2, ensure_ascii=False))

    print("\n✅ Тест завершен!")


if __name__ == "__main__":
    asyncio.run(main())
