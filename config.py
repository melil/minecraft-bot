from dotenv import load_dotenv
import os

load_dotenv()

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
TIMEWEB_TOKEN = os.getenv("TIMEWEB_TOKEN")

if not TELEGRAM_TOKEN or not TIMEWEB_TOKEN:
    raise RuntimeError("ENV tokens not found")

SERVER_ID = os.getenv("SERVER_ID")
SERVER_B_IP = os.getenv("SERVER_B_IP")
SERVER_B_SSH = f"root@{SERVER_B_IP}"
