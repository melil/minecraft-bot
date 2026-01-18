#!/usr/bin/env python3
"""
Тестовый скрипт для проверки мониторинга логов Minecraft
"""
import asyncio
import logging
from telegram import Bot
from core.config import MINECRAFT_SERVER_SSH, TELEGRAM_TOKEN
from core.minecraft.log_monitor import MinecraftLogMonitor, MinecraftEvent, TelegramMessageEvent

# Настройка логирования
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# ID группы для тестирования (можно передать как аргумент)
TEST_GROUP_ID = -5142213077  # Замените на ваш ID группы если нужно

# Telegram Bot для отправки сообщений
bot = None


async def test_event_handler(event: MinecraftEvent):
    """Тестовый обработчик событий с отправкой в Telegram"""
    logger.info(f"🎯 Получено событие: {event.event_type}")
    
    if hasattr(event, 'player_name'):
        logger.info(f"   👤 Игрок: {event.player_name}")
    
    if hasattr(event, 'message'):
        logger.info(f"   💬 Сообщение: {event.message}")
    
    formatted_message = event.format_telegram()
    logger.info(f"   📨 Форматированное: {formatted_message}")
    
    # Отправляем в Telegram только сообщения с префиксом telegram:
    if isinstance(event, TelegramMessageEvent):
        try:
            logger.info(f"📤 Отправка в Telegram группу {TEST_GROUP_ID}...")
            await bot.send_message(
                chat_id=TEST_GROUP_ID,
                text=formatted_message,
                parse_mode='HTML'
            )
            logger.info("✅ Сообщение успешно отправлено в Telegram!")
        except Exception as e:
            logger.error(f"❌ Ошибка отправки в Telegram: {e}", exc_info=True)


async def main():
    """Главная функция тестирования"""
    global bot
    
    print("\n" + "="*60)
    print("🧪 ТЕСТИРОВАНИЕ МОНИТОРИНГА ЛОГОВ MINECRAFT")
    print("="*60 + "\n")
    
    print("📋 Конфигурация:")
    print(f"   SSH Host: {MINECRAFT_SERVER_SSH['host']}")
    print(f"   SSH User: {MINECRAFT_SERVER_SSH['user']}")
    print(f"   SSH Port: {MINECRAFT_SERVER_SSH['port']}")
    print(f"   Test Group ID: {TEST_GROUP_ID}")
    print()
    
    # Инициализируем бота
    print("🤖 Инициализация Telegram бота...")
    bot = Bot(token=TELEGRAM_TOKEN)
    print("✅ Бот инициализирован")
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
    print("   3. Обычные сообщения НЕ будут отправлены в Telegram")
    print("   4. Сообщения с 'telegram:' будут отправлены в группу")
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
