#!/usr/bin/env python3
"""
Тестовый скрипт для проверки мониторинга логов Minecraft
"""
import asyncio
import logging
from core.config import MINECRAFT_SERVER_SSH
from core.minecraft.log_monitor import MinecraftLogMonitor, MinecraftEvent

# Настройка логирования
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# ID группы для тестирования (можно передать как аргумент)
TEST_GROUP_ID = -5142213077  # Замените на ваш ID группы если нужно


async def test_event_handler(event: MinecraftEvent):
    """Тестовый обработчик событий"""
    logger.info(f"🎯 Получено событие: {event.event_type}")
    
    if hasattr(event, 'player_name'):
        logger.info(f"   👤 Игрок: {event.player_name}")
    
    if hasattr(event, 'message'):
        logger.info(f"   💬 Сообщение: {event.message}")
    
    logger.info(f"   📨 Форматированное: {event.format_telegram()}")


async def main():
    """Главная функция тестирования"""
    print("\n" + "="*60)
    print("🧪 ТЕСТИРОВАНИЕ МОНИТОРИНГА ЛОГОВ MINECRAFT")
    print("="*60 + "\n")
    
    print("📋 Конфигурация:")
    print(f"   SSH Host: {MINECRAFT_SERVER_SSH['host']}")
    print(f"   SSH User: {MINECRAFT_SERVER_SSH['user']}")
    print(f"   SSH Port: {MINECRAFT_SERVER_SSH['port']}")
    print(f"   Test Group ID: {TEST_GROUP_ID}")
    print()
    
    # Создаем монитор
    print("🔧 Создание мониторинга логов...")
    monitor = MinecraftLogMonitor(
        ssh_config=MINECRAFT_SERVER_SSH,
        event_callback=test_event_handler,
        check_interval=2
    )
    
    # Запускаем
    print("▶️  Запуск мониторинга...")
    await monitor.start()
    
    print(f"✅ Мониторинг запущен (is_running={monitor.is_running})")
    print()
    print("="*60)
    print("⏰ МОНИТОРИНГ АКТИВЕН - наблюдайте за событиями")
    print("="*60)
    print()
    print("💡 Инструкция:")
    print("   1. Зайдите на Minecraft сервер")
    print("   2. Напишите в чат: telegram: Тестовое сообщение")
    print("   3. Напишите обычное сообщение: Привет всем")
    print("   4. Выйдите и зайдите снова")
    print()
    print("📊 События будут отображаться здесь в реальном времени...")
    print("   Нажмите Ctrl+C для остановки")
    print()
    
    try:
        # Работаем 5 минут
        await asyncio.sleep(300)
    except KeyboardInterrupt:
        print("\n\n⏹️  Остановка по запросу пользователя...")
    
    # Останавливаем
    print("🛑 Остановка мониторинга...")
    await monitor.stop()
    
    print("\n" + "="*60)
    print("✅ ТЕСТ ЗАВЕРШЁН")
    print("="*60 + "\n")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except Exception as e:
        logger.error(f"❌ Ошибка: {e}", exc_info=True)
