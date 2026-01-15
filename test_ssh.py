#!/usr/bin/env python3
import asyncio
import logging
from core.ssh.client import SSHClient
from core.config import MINECRAFT_SERVER_SSH

# Настройка логирования
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)


async def main():
    print("🧪 Тест SSH клиента\n")

    # Создаем клиент
    client = SSHClient(**MINECRAFT_SERVER_SSH)
    print(f"Клиент: {client}\n")

    # 1. Проверка доступности
    print("1️⃣ Проверка доступности...")
    is_available = await client.is_available()
    print(f"   Результат: {'✅ Доступен' if is_available else '❌ Недоступен'}\n")

    if not is_available:
        print("❌ Сервер недоступен. Проверьте настройки в .env")
        return

    # 2. Тест соединения с задержкой
    print("2️⃣ Тест соединения с измерением задержки...")
    test_result = await client.test_connection()
    print(f"   Доступен: {test_result['available']}")
    print(f"   Задержка: {test_result['latency_ms']}ms")
    print(f"   Ошибка: {test_result['error']}\n")

    # 3. Выполнение команд
    print("3️⃣ Выполнение команд...")

    commands = [
        ("uname -a", "Информация о системе"),
        ("whoami", "Текущий пользователь"),
        ("pwd", "Текущая директория"),
        ("systemctl is-active minecraft.service", "Статус Minecraft")
    ]

    for cmd, description in commands:
        try:
            print(f"   📝 {description}: {cmd}")
            result = await client.execute(cmd, timeout=10)
            print(f"   ✅ {result}\n")
        except Exception as e:
            print(f"   ❌ Ошибка: {e}\n")

    print("✅ Тесты завершены!")


if __name__ == "__main__":
    asyncio.run(main())