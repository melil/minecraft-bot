import os
from dotenv import load_dotenv

load_dotenv()

# Telegram
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")

# REG.RU Cloud API (переименовано для ясности)
REGRU_CLOUD_TOKEN = os.getenv("TIMEWEB_TOKEN")  # Используем старое имя переменной
MINECRAFT_SERVER_ID = os.getenv("MINECRAFT_SERVER_ID")

# SSH Configuration
MINECRAFT_SERVER_SSH_STRING = os.getenv("MINECRAFT_SERVER_SSH")

MINECRAFT_RCON_PASSWORD = os.getenv('MINECRAFT_RCON_PASSWORD', 'SuperPassword228')

if MINECRAFT_SERVER_SSH_STRING:
    try:
        if "@" in MINECRAFT_SERVER_SSH_STRING:
            ssh_parts = MINECRAFT_SERVER_SSH_STRING.split("@")
            ssh_user = ssh_parts[0].strip()
            ssh_host_port = ssh_parts[1].strip().split(":")
            ssh_host = ssh_host_port[0].strip()
            ssh_port = int(ssh_host_port[1]) if len(ssh_host_port) > 1 else 22
        else:
            ssh_host = MINECRAFT_SERVER_SSH_STRING.strip()
            ssh_user = "root"
            ssh_port = 22
    except Exception as e:
        raise ValueError(f"Неверный формат MINECRAFT_SERVER_SSH: {MINECRAFT_SERVER_SSH_STRING}")
else:
    ssh_host = os.getenv("MINECRAFT_SERVER_HOST", "").strip()
    ssh_user = os.getenv("MINECRAFT_SERVER_USER", "root").strip()
    ssh_port_str = os.getenv("MINECRAFT_SERVER_PORT", "22").strip()
    try:
        ssh_port = int(ssh_port_str)
    except ValueError:
        ssh_port = 22

MINECRAFT_SERVER_SSH = {
    "host": ssh_host,
    "user": ssh_user,
    "port": ssh_port,
    "key_file": os.getenv("MINECRAFT_SERVER_KEY_FILE")
}

# Валидация
errors = []

if not TELEGRAM_TOKEN or TELEGRAM_TOKEN.strip() == "":
    errors.append("TELEGRAM_TOKEN не установлен")

if not REGRU_CLOUD_TOKEN or REGRU_CLOUD_TOKEN.strip() == "":
    errors.append("TIMEWEB_TOKEN (REG.RU Cloud API Token) не установлен")

if not MINECRAFT_SERVER_ID or MINECRAFT_SERVER_ID.strip() == "":
    errors.append("MINECRAFT_SERVER_ID не установлен")

if not ssh_host or ssh_host == "":
    errors.append("SSH конфигурация не установлена")

if errors:
    error_message = "❌ Ошибки в .env файле:\n" + "\n".join(f"  • {e}" for e in errors)
    raise ValueError(error_message)

# Успешная загрузка
print("=" * 60)
print("✅ Конфигурация успешно загружена")
print("=" * 60)
print(f"📡 Telegram Bot: настроен")
print(f"☁️  REG.RU Cloud API: настроен")
print(f"🖥️  Server ID: {MINECRAFT_SERVER_ID}")
print(f"🔐 SSH: {MINECRAFT_SERVER_SSH['user']}@{MINECRAFT_SERVER_SSH['host']}:{MINECRAFT_SERVER_SSH['port']}")
if MINECRAFT_SERVER_SSH['key_file']:
    print(f"🔑 SSH Key: {MINECRAFT_SERVER_SSH['key_file']}")
print("=" * 60)