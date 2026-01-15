# test_minecraft_methods.py
import asyncio
from core.ssh.client import SSHClient
from core.minecraft.service import (
    get_players_via_rcon,
    get_players_via_logs,
    get_players_via_connections
)
from core.config import MINECRAFT_SERVER_SSH


async def main():
    print("🧪 Тест различных методов подсчета игроков\n")

    client = SSHClient(**MINECRAFT_SERVER_SSH)

    # Метод 1: RCON
    print("1️⃣ Тест RCON...")
    players, max_p, names = await get_players_via_rcon(client)
    if players is not None:
        print(f"   ✅ Игроков: {players}/{max_p}")
        print(f"   Имена: {names}")
    else:
        print(f"   ❌ RCON недоступен")

    # Метод 2: Логи
    print("\n2️⃣ Тест логов journalctl...")
    players, max_p, names = await get_players_via_logs(client)
    print(f"   Игроков: {players}/{max_p}")
    print(f"   Имена: {names}")

    # Метод 3: TCP соединения
    print("\n3️⃣ Тест TCP соединений...")
    players = await get_players_via_connections(client)
    print(f"   Соединений: {players}")

    print("\n" + "=" * 50)


if __name__ == "__main__":
    asyncio.run(main())