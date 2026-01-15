#!/usr/bin/env python3
import asyncio
from core.minecraft.service import get_minecraft_status
from core.config import MINECRAFT_SERVER_SSH

async def main():
    print("🧪 Тест статуса Minecraft (без tmux)\n")

    print("Получение статуса...")
    status = await get_minecraft_status(MINECRAFT_SERVER_SSH)

    print(f"\n📊 Результат:")
    print(f"  Активен: {status['active']}")
    print(f"  Игроков: {status['players']}/{status['max_players']}")
    print(f"  Имена: {status['names']}")

    if status['active']:
        print("\n✅ Minecraft работает!")
    else:
        print("\n⚫ Minecraft не запущен")

if __name__ == "__main__":
    asyncio.run(main())