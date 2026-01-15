import os
from dotenv import load_dotenv

load_dotenv()

# Telegram
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")

# TimeWeb Cloud API
TIMEWEB_TOKEN = os.getenv("TIMEWEB_TOKEN")
MINECRAFT_SERVER_ID = os.getenv("MINECRAFT_SERVER_ID")

# SSH Configuration
MINECRAFT_SERVER_SSH = {
    "host": os.getenv("MINECRAFT_SERVER_HOST", "95.163.227.185"),
    "user": os.getenv("MINECRAFT_SERVER_USER", "root"),
    "port": int(os.getenv("MINECRAFT_SERVER_PORT", "22")),
    "key_file": os.getenv("MINECRAFT_SERVER_KEY_FILE")  # Опционально
}

# Валидация
if not TELEGRAM_TOKEN:
    raise ValueError("TELEGRAM_TOKEN не установлен в .env")

if not TIMEWEB_TOKEN:
    raise ValueError("TIMEWEB_TOKEN не установлен в .env")

if not MINECRAFT_SERVER_ID:
    raise ValueError("MINECRAFT_SERVER_ID не установлен в .env")

if not MINECRAFT_SERVER_SSH["host"] or MINECRAFT_SERVER_SSH["host"] == "95.163.227.185":
    raise ValueError("MINECRAFT_SERVER_HOST не установлен в .env")