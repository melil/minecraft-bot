#!/usr/bin/env python3
"""
Тестовый скрипт для проверки RCON функционала
"""
import asyncio
import logging
from core.config import MINECRAFT_SERVER_SSH, MINECRAFT_RCON_PASSWORD
from core.minecraft.rcon import execute_rcon_command, say, list_players
from core.minecraft.service import is_ready

logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


async def test_rcon():
    """Тестирование RCON команд"""
    
    print("\n" + "="*60)
    print("🧪 ТЕСТИРОВАНИЕ RCON ФУНКЦИОНАЛА")
    print("="*60 + "\n")
    
    # Тест 1: Проверка доступности сервера
    print("1️⃣ Проверка доступности Minecraft сервера...")
    ready = await is_ready(MINECRAFT_SERVER_SSH)
    
    if not ready:
        print("❌ Сервер не запущен или RCON недоступен")
        print("   Запустите сервер и попробуйте снова")
        return
    
    print("✅ Сервер доступен через RCON\n")
    
    # Тест 2: Список игроков
    print("2️⃣ Получение списка игроков...")
    result = await execute_rcon_command(MINECRAFT_SERVER_SSH, "list")
    if result:
        print(f"✅ Ответ: {result}")
    else:
        print("❌ Не удалось получить список игроков")
    print()
    
    # Тест 3: Отправка тестового сообщения
    print("3️⃣ Отправка тестового сообщения...")
    success = await say(
        MINECRAFT_SERVER_SSH,
        "Это тестовое сообщение из Python скрипта!",
        sender="TestBot"
    )
    
    if success:
        print("✅ Сообщение отправлено в игру")
        print("   Проверьте игровой чат!")
    else:
        print("❌ Не удалось отправить сообщение")
    print()
    
    # Тест 4: Время суток
    print("4️⃣ Получение времени суток...")
    result = await execute_rcon_command(MINECRAFT_SERVER_SSH, "time query daytime")
    if result:
        print(f"✅ Ответ: {result}")
    else:
        print("❌ Не удалось получить время")
    print()
    
    # Тест 5: Версия сервера
    print("5️⃣ Получение версии сервера...")
    result = await execute_rcon_command(MINECRAFT_SERVER_SSH, "version")
    if result:
        print(f"✅ Ответ: {result}")
    else:
        print("❌ Не удалось получить версию")
    print()
    
    # Тест 6: Список игроков через функцию
    print("6️⃣ Получение списка игроков через list_players()...")
    players = await list_players(MINECRAFT_SERVER_SSH)
    if players is not None:
        if players:
            print(f"✅ Игроки онлайн: {', '.join(players)}")
        else:
            print("✅ Нет игроков онлайн")
    else:
        print("❌ Не удалось получить список")
    print()
    
    print("="*60)
    print("✅ ТЕСТИРОВАНИЕ ЗАВЕРШЕНО")
    print("="*60 + "\n")
    
    print("💡 Что проверить дальше:")
    print("   1. Запустите бота: python bot.py")
    print("   2. Отправьте команду: /say Привет из Telegram! (нужны права админа)")
    print("   3. Проверьте, что сообщение появилось в игре")
    print("   4. Отправьте команду: /rcon time set day (нужны права СУПЕР-АДМИНА)")
    print("   5. Напишите что-то в игровой чат")
    print("   6. Включите мониторинг событий в настройках бота")
    print("   7. Проверьте, что сообщение пришло в Telegram группу\n")


async def test_log_parsing():
    """Тестирование парсинга логов"""
    from core.minecraft.log_monitor import MinecraftLogParser
    
    print("\n" + "="*60)
    print("🧪 ТЕСТИРОВАНИЕ ПАРСИНГА ЛОГОВ")
    print("="*60 + "\n")
    
    # Тестовые строки логов
    test_logs = [
        "[12:34:56] [Server thread/INFO]: Player123 joined the game",
        "[12:35:10] [Server thread/INFO]: <Player123> Hello world!",
        "[12:36:00] [Server thread/INFO]: Player123 has made the advancement [Stone Age]",
        "[12:37:30] [Server thread/INFO]: Player123 was slain by Zombie",
        "[12:38:00] [Server thread/INFO]: Player123 left the game",
    ]
    
    parser = MinecraftLogParser()
    
    for i, log_line in enumerate(test_logs, 1):
        print(f"{i}️⃣ Парсинг: {log_line}")
        event = parser.parse_line(log_line)
        
        if event:
            print(f"   ✅ Тип: {event.event_type}")
            print(f"   📝 Форматированное: {event.format_telegram()}")
        else:
            print("   ❌ Событие не распознано")
        print()
    
    print("="*60)
    print("✅ ТЕСТИРОВАНИЕ ПАРСИНГА ЗАВЕРШЕНО")
    print("="*60 + "\n")


async def main():
    """Главная функция"""
    print("\n🚀 Запуск тестов RCON и парсинга логов\n")
    
    try:
        # Тест RCON
        await test_rcon()
        
        # Тест парсинга
        await test_log_parsing()
        
    except Exception as e:
        print(f"\n❌ Ошибка: {e}")
        logger.exception("Ошибка в тестах")


if __name__ == "__main__":
    asyncio.run(main())
