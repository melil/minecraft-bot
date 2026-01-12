from dotenv import load_dotenv
import os

load_dotenv()

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
TIMEWEB_TOKEN = os.getenv("TIMEWEB_TOKEN")

if not TELEGRAM_TOKEN or not TIMEWEB_TOKEN:
    raise RuntimeError("ENV tokens not found")

MINECRAFT_SERVER_ID = os.getenv("MINECRAFT_SERVER_ID")
MINECRAFT_SERVER_IP = os.getenv("MINECRAFT_SERVER_IP")
MINECRAFT_SERVER_SSH = f"root@{MINECRAFT_SERVER_IP}"
