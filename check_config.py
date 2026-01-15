#!/usr/bin/env python3
"""Проверка конфигурации бота"""

import os
import sys
from pathlib import Path


def check_env_file():
    """Проверяет наличие .env файла"""
    env_path = Path(".env")

    if not env_path.exists():
        print("❌ Файл .env не найден!")
        print("\n📝 Создайте файл .env со следующими параметрами:")
        print("""
# Telegram Bot
TELEGRAM_TOKEN=your_bot_token

# TimeWeb Cloud API
TIMEWEB_TOKEN=your_timeweb_token
MINECRAFT_SERVER_ID=your_server_id

# SSH Configuration
MINECRAFT_SERVER_SSH=root@your-server-ip:22
        """)
        return False

    print("✅ Файл .env найден")
    return True


def check_required_vars():
    """Проверяет обязательные переменные"""
    from dotenv import load_dotenv
    load_dotenv()

    required_vars = {
        "TELEGRAM_TOKEN": "Токен Telegram бота",
        "TIMEWEB_TOKEN": "API токен TimeWeb",
        "MINECRAFT_SERVER_ID": "ID сервера в TimeWeb"
    }

    ssh_var = os.getenv("MINECRAFT_SERVER_SSH")
    host_var = os.getenv("MINECRAFT_SERVER_HOST")

    print("\n🔍 Проверка переменных окружения:")

    all_ok = True
    for var, description in required_vars.items():
        value = os.getenv(var)
        if value:
            # Маскируем токены
            if "TOKEN" in var:
                display_value = f"{value[:10]}...{value[-5:]}" if len(value) > 15 else "***"
            else:
                display_value = value
            print(f"   ✅ {var}: {display_value}")
        else:
            print(f"   ❌ {var}: не установлен ({description})")
            all_ok = False

    # Проверка SSH конфигурации
    if ssh_var:
        print(f"   ✅ MINECRAFT_SERVER_SSH: {ssh_var}")
    elif host_var:
        user = os.getenv("MINECRAFT_SERVER_USER", "root")
        port = os.getenv("MINECRAFT_SERVER_PORT", "22")
        print(f"   ✅ SSH конфигурация: {user}@{host_var}:{port}")
    else:
        print(f"   ❌ SSH конфигурация не установлена")
        print(f"      Добавьте MINECRAFT_SERVER_SSH=user@host:port")
        print(f"      или MINECRAFT_SERVER_HOST=host")
        all_ok = False

    # Опциональные параметры
    key_file = os.getenv("MINECRAFT_SERVER_KEY_FILE")
    if key_file:
        if Path(key_file).exists():
            print(f"   ✅ MINECRAFT_SERVER_KEY_FILE: {key_file}")
        else:
            print(f"   ⚠️  MINECRAFT_SERVER_KEY_FILE: {key_file} (файл не найден)")

    return all_ok


def try_load_config():
    """Пытается загрузить конфигурацию"""
    print("\n🚀 Попытка загрузки конфигурации...")

    try:
        from core.config import (
            TELEGRAM_TOKEN,
            TIMEWEB_TOKEN,
            MINECRAFT_SERVER_ID,
            MINECRAFT_SERVER_SSH
        )

        print("✅ Конфигурация успешно загружена!")
        print(f"\n📊 Детали:")
        print(f"   Server ID: {MINECRAFT_SERVER_ID}")
        print(f"   SSH: {MINECRAFT_SERVER_SSH['user']}@{MINECRAFT_SERVER_SSH['host']}:{MINECRAFT_SERVER_SSH['port']}")

        return True

    except ValueError as e:
        print(f"❌ Ошибка загрузки конфигурации:")
        print(f"   {e}")
        return False
    except Exception as e:
        print(f"❌ Неожиданная ошибка:")
        print(f"   {e}")
        return False


def main():
    """Основная функция"""
    print("=" * 50)
    print("🔧 ПРОВЕРКА КОНФИГУРАЦИИ MINECRAFT BOT")
    print("=" * 50)

    # Шаг 1: Проверка .env файла
    if not check_env_file():
        sys.exit(1)

    # Шаг 2: Проверка переменных
    if not check_required_vars():
        print("\n❌ Не все обязательные переменные установлены")
        sys.exit(1)

    # Шаг 3: Загрузка конфигурации
    if not try_load_config():
        sys.exit(1)

    print("\n" + "=" * 50)
    print("✅ ВСЕ ПРОВЕРКИ ПРОЙДЕНЫ!")
    print("=" * 50)
    print("\n💡 Можно запускать бота: python3 bot.py")


if __name__ == "__main__":
    main()