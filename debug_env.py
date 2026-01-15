#!/usr/bin/env python3
"""Отладка загрузки переменных окружения"""

import os
from dotenv import load_dotenv

print("🔍 Отладка .env файла\n")

# Проверка наличия файла
if os.path.exists(".env"):
    print("✅ Файл .env найден\n")

    # Показываем содержимое (без токенов)
    print("📄 Содержимое .env:")
    with open(".env", "r") as f:
        for i, line in enumerate(f, 1):
            line = line.strip()
            if line and not line.startswith("#"):
                # Маскируем токены
                if "TOKEN=" in line:
                    parts = line.split("=")
                    print(f"   {i}: {parts[0]}=***")
                else:
                    print(f"   {i}: {line}")
            elif line:
                print(f"   {i}: {line}")
    print()
else:
    print("❌ Файл .env НЕ найден!\n")

# Загружаем переменные
load_dotenv()

# Проверяем загрузку
print("🔍 Загруженные переменные:")

vars_to_check = [
    "TELEGRAM_TOKEN",
    "TIMEWEB_TOKEN",
    "MINECRAFT_SERVER_ID",
    "MINECRAFT_SERVER_SSH",
    "MINECRAFT_SERVER_HOST",
    "MINECRAFT_SERVER_USER",
    "MINECRAFT_SERVER_PORT"
]

for var in vars_to_check:
    value = os.getenv(var)
    if value:
        # Маскируем токены
        if "TOKEN" in var:
            display = f"{value[:10]}...{value[-5:]}" if len(value) > 15 else "***"
        else:
            display = value
        print(f"   ✅ {var} = {display}")
    else:
        print(f"   ❌ {var} = не установлен")

print("\n" + "=" * 60)

# Пытаемся создать SSH конфиг
ssh_string = os.getenv("MINECRAFT_SERVER_SSH")
ssh_host = os.getenv("MINECRAFT_SERVER_HOST")

print("🔧 Определение SSH конфигурации:")

if ssh_string:
    print(f"   Используется MINECRAFT_SERVER_SSH: {ssh_string}")
elif ssh_host:
    user = os.getenv("MINECRAFT_SERVER_USER", "root")
    port = os.getenv("MINECRAFT_SERVER_PORT", "22")
    print(f"   Используется раздельный формат:")
    print(f"     HOST: {ssh_host}")
    print(f"     USER: {user}")
    print(f"     PORT: {port}")
else:
    print(f"   ❌ SSH конфигурация не найдена!")

print("=" * 60)