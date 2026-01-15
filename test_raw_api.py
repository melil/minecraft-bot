# test_raw_api.py
import asyncio
import aiohttp
from core.config import REGRU_CLOUD_TOKEN, MINECRAFT_SERVER_ID


async def test_api():
    """Прямой тест API без обработки"""

    # Попробуем разные эндпоинты
    endpoints = [
        f"https://api.timeweb.cloud/api/v1/servers/{MINECRAFT_SERVER_ID}",
        f"https://api.timeweb.cloud/api/v1/vps/{MINECRAFT_SERVER_ID}",
        f"https://api.timeweb.cloud/api/v1/cloud-servers/{MINECRAFT_SERVER_ID}",
    ]

    headers = {
        "Authorization": f"Bearer {REGRU_CLOUD_TOKEN}",
        "Content-Type": "application/json"
    }

    async with aiohttp.ClientSession() as session:
        for i, url in enumerate(endpoints, 1):
            print(f"\n{'=' * 60}")
            print(f"Тест {i}: {url}")
            print('=' * 60)

            try:
                async with session.get(url, headers=headers) as resp:
                    print(f"Status: {resp.status}")

                    if resp.status == 200:
                        data = await resp.json()

                        # Ищем поле server
                        if 'server' in data:
                            server_data = data['server']
                            print(f"\n✅ Найден объект 'server':")
                            print(f"  state: {server_data.get('state')}")
                            print(f"  status: {server_data.get('status')}")
                            print(f"  ip: {server_data.get('main_ipv4')}")
                        else:
                            print(f"\n⚠️ Прямой ответ (без 'server'):")
                            print(f"  state: {data.get('state')}")
                            print(f"  status: {data.get('status')}")
                    else:
                        text = await resp.text()
                        print(f"❌ Ошибка: {text}")

            except Exception as e:
                print(f"❌ Исключение: {e}")


if __name__ == "__main__":
    asyncio.run(test_api())