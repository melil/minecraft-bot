#!/usr/bin/env python3
import asyncio
import logging
import subprocess
import os
import re
from typing import Set
import aiohttp
from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    filters,
    ContextTypes
)
from server_monitor import ServerMonitor
from config import TELEGRAM_TOKEN, TIMEWEB_TOKEN, SERVER_ID, SERVER_B_IP, SERVER_B_SSH

ADMIN_IDS_FILE = "/root/minecraft-bot/admins.txt"

# Глобальные переменные
ADMIN_USER_IDS = set()

monitor = ServerMonitor()

# Настройка логирования
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

def load_admin_ids():
    """Загружает список администраторов из файла"""
    global ADMIN_USER_IDS
    try:
        if os.path.exists(ADMIN_IDS_FILE):
            with open(ADMIN_IDS_FILE, 'r') as f:
                ADMIN_USER_IDS = set(int(line.strip()) for line in f if line.strip())
        else:
            # Создаем файл с пустым списком
            with open(ADMIN_IDS_FILE, 'w') as f:
                pass
    except Exception as e:
        logger.error(f"Ошибка загрузки admin IDs: {e}")

def save_admin_ids():
    """Сохраняет список администраторов в файл"""
    try:
        with open(ADMIN_IDS_FILE, 'w') as f:
            for admin_id in ADMIN_USER_IDS:
                f.write(f"{admin_id}\n")
    except Exception as e:
        logger.error(f"Ошибка сохранения admin IDs: {e}")

def is_admin(user_id: int) -> bool:
    """Проверяет, является ли пользователь администратором"""
    return user_id in ADMIN_USER_IDS

async def start_server_via_api() -> str:
    """Запускает сервер Б через API TimeWeb"""
    try:
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {TIMEWEB_TOKEN}"
        }
        url = f"https://api.timeweb.cloud/api/v1/servers/{SERVER_ID}/start"
        
        async with aiohttp.ClientSession() as session:
            async with session.post(url, headers=headers) as response:
                if response.status == 204:
                    return "✅ Команда на запуск облака отправлена\n⏳ Ожидайте 2-3 минуты для полной загрузки"
                else:
                    error_text = await response.text()
                    return f"❌ Ошибка API ({response.status}): {error_text}"
    except Exception as e:
        return f"❌ Ошибка при запуске сервера: {str(e)}"

async def execute_ssh_command(command: str) -> str:
    try:
        proc = await asyncio.create_subprocess_shell(
            f"ssh -o ConnectTimeout=10 -o StrictHostKeyChecking=no {SERVER_B_SSH} '{command}'",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )

        stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=20)

        if proc.returncode == 0:
            return stdout.decode().strip()
        else:
            return f"❌ SSH error: {stderr.decode().strip()}"
    except asyncio.TimeoutError:
        return "❌ SSH timeout"
    except Exception as e:
        return f"❌ SSH exception: {e}"

async def is_minecraft_ready() -> bool:
    result = await execute_ssh_command("nc -z localhost 25565 && echo READY")
    return "READY" in result

async def wait_until_playable(monitor: ServerMonitor, timeout=300):
    start = asyncio.get_event_loop().time()

    while asyncio.get_event_loop().time() - start < timeout:
        if await monitor.minecraft_ready():
            return True
        await asyncio.sleep(10)

    return False

async def check_server_status() -> str:
    """Проверяет статус сервера Б и Minecraft"""
    try:
        # Сначала проверяем доступность через SSH
        ssh_test = await execute_ssh_command("echo 'SSH_TEST' && date '+%H:%M:%S'")
        
        if "SSH_TEST" not in ssh_test or "❌" in ssh_test:
            # Если SSH недоступен, проверяем через API
            try:
                headers = {"Authorization": f"Bearer {TIMEWEB_TOKEN}"}
                url = f"https://api.timeweb.cloud/api/v1/servers/{SERVER_ID}"
                
                async with aiohttp.ClientSession() as session:
                    async with session.get(url, headers=headers) as response:
                        if response.status == 200:
                            data = await response.json()
                            server_status = data.get('server', {}).get('status', 'unknown')
                            return f"🚫 Сервер Minecraft выключен (статус: {server_status})"
            except:
                pass
            return "🚫 Сервер Minecraft выключен или недоступен"
        
        # Если SSH доступен, проверяем Minecraft
        players_output = await execute_ssh_command("/root/scripts/players.sh")
        
        # Парсим вывод players.sh
        if "There are 0" in players_output or "There are 0 of a max" in players_output:
            return "✅ Сервер запущен\n👥 Игроков онлайн: 0"
        
        # Ищем количество игроков
        match = re.search(r'There are (\d+) of a max of (\d+)', players_output)
        if match:
            current_players = match.group(1)
            max_players = match.group(2)
            
            # Ищем имена игроков
            player_names = ""
            if "players online:" in players_output:
                parts = players_output.split("players online:")
                if len(parts) > 1:
                    names = parts[1].strip()
                    if names and names != ".":
                        # Убираем точку в конце если есть
                        if names.endswith('.'):
                            names = names[:-1]
                        player_names = f"\n👤 Игроки: {names}"
            
            return f"✅ Сервер запущен\n👥 Игроков: {current_players}/{max_players}{player_names}"
        
        # Если другой формат вывода
        if "There are" in players_output:
            return f"✅ Сервер запущен\n📊 {players_output}"
        
        # Проверяем статус Minecraft сервиса
        mc_status = await execute_ssh_command("systemctl is-active minecraft 2>/dev/null || echo 'inactive'")
        if "active" in mc_status:
            return "✅ Сервер запущен\n🎮 Minecraft: активен"
        elif "inactive" in mc_status:
            return "✅ Сервер Б запущен\n🎮 Minecraft: не запущен"
        
        return f"✅ Сервер Б доступен\nℹ️ {players_output[:200]}"
        
    except Exception as e:
        logger.error(f"Ошибка проверки статуса: {e}")
        return f"❌ Ошибка проверки: {str(e)}"

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик команды /start"""
    user = update.effective_user
    chat = update.effective_chat
    
    if chat.type == "private":
        welcome_text = (
            "👋 Привет! Я бот для управления Minecraft сервером.\n\n"
            "📋 Доступные команды:\n"
            "/status - статус сервера\n"
            "/players - список игроков онлайн\n"
            "/start_server - запустить сервер (админы)\n"
            "/stop_server - остановить сервер (админы)\n"
            "/restart_server - перезагрузить сервер (админы)\n\n"
            "👑 Команды для администраторов:\n"
            "/add_admin <id> - добавить администратора\n"
            "/list_admins - список администраторов\n"
            "/del_admin <id> - удалить администратора\n\n"
            "⚠️ Команды с пометкой (админы) доступны только в личных сообщениях."
        )
        await update.message.reply_text(welcome_text)
    else:
        await update.message.reply_text(
            "🤖 Бот Minecraft сервера активен.\n"
            "Используйте /players для проверки игроков онлайн."
        )

async def players_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик команды /players (доступна везде)"""
    status_msg = await update.message.reply_text("⏳ Проверяю игроков онлайн...")
    status = await check_server_status()
    await status_msg.edit_text(status)

async def start_server_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_chat.type != "private":
        return

    if not is_admin(update.effective_user.id):
        await update.message.reply_text("❌ Нет прав")
        return

    await update.message.reply_text("☁️ Запускаю сервер в облаке...")

    await start_server_via_api()

    await update.message.reply_text("⏳ Жду пока Minecraft станет доступен...")

    if await wait_until_playable(monitor):
        await update.message.reply_text(
            "🎮 Minecraft сервер ГОТОВ!\n"
            "✅ Можно заходить и играть"
        )
    else:
        await update.message.reply_text(
            "⚠️ Сервер не стал доступен за 5 минут"
        )    


async def stop_server_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик команды /stop_server (только для админов в ЛС)"""
    chat = update.effective_chat
    user = update.effective_user
    
    if chat.type != "private":
        await update.message.reply_text("⚠️ Эта команда доступна только в личных сообщениях.")
        return
    
    if not is_admin(user.id):
        await update.message.reply_text("❌ У вас нет прав для выполнения этой команды.")
        return
    
    status_msg = await update.message.reply_text("⏳ Останавливаю Minecraft сервер...")
    result = await execute_ssh_command("/root/scripts/stop_server_manually.sh")
    await status_msg.edit_text(result)

async def restart_server_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик команды /restart_server (только для админов в ЛС)"""
    chat = update.effective_chat
    user = update.effective_user
    
    if chat.type != "private":
        await update.message.reply_text("⚠️ Эта команда доступна только в личных сообщениях.")
        return
    
    if not is_admin(user.id):
        await update.message.reply_text("❌ У вас нет прав для выполнения этой команды.")
        return
    
    status_msg = await update.message.reply_text("⏳ Перезагружаю Minecraft сервер...")
    result = await execute_ssh_command("/root/scripts/reboot_server_manually.sh")
    await status_msg.edit_text(result)
    
    # Ждем и проверяем статус
    await asyncio.sleep(30)
    status = await check_server_status()
    await update.message.reply_text(f"📊 Статус после перезагрузки:\n{status}")

async def status_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = await update.message.reply_text("⏳ Проверяю статус...")
    status = await monitor.full_status()
    await msg.edit_text(status)

async def add_admin_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Добавляет администратора"""
    chat = update.effective_chat
    user = update.effective_user
    
    if chat.type != "private":
        return
    
    if not is_admin(user.id):
        await update.message.reply_text("❌ У вас нет прав для выполнения этой команды.")
        return
    
    if not context.args:
        await update.message.reply_text("Использование: /add_admin <user_id>")
        return
    
    try:
        new_admin_id = int(context.args[0])
        ADMIN_USER_IDS.add(new_admin_id)
        save_admin_ids()
        await update.message.reply_text(f"✅ Пользователь {new_admin_id} добавлен в администраторы.")
    except ValueError:
        await update.message.reply_text("❌ Неверный ID пользователя.")

async def del_admin_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Удаляет администратора"""
    chat = update.effective_chat
    user = update.effective_user
    
    if chat.type != "private":
        return
    
    if not is_admin(user.id):
        await update.message.reply_text("❌ У вас нет прав для выполнения этой команды.")
        return
    
    if not context.args:
        await update.message.reply_text("Использование: /del_admin <user_id>")
        return
    
    try:
        del_admin_id = int(context.args[0])
        if del_admin_id == user.id:
            await update.message.reply_text("❌ Нельзя удалить самого себя.")
            return
        
        if del_admin_id in ADMIN_USER_IDS:
            ADMIN_USER_IDS.remove(del_admin_id)
            save_admin_ids()
            await update.message.reply_text(f"✅ Пользователь {del_admin_id} удален из администраторов.")
        else:
            await update.message.reply_text(f"❌ Пользователь {del_admin_id} не найден в списке администраторов.")
    except ValueError:
        await update.message.reply_text("❌ Неверный ID пользователя.")

async def list_admins_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показывает список администраторов"""
    chat = update.effective_chat
    user = update.effective_user
    
    if chat.type != "private":
        return
    
    if not is_admin(user.id):
        await update.message.reply_text("❌ У вас нет прав для выполнения этой команды.")
        return
    
    if ADMIN_USER_IDS:
        admins_list = "\n".join(f"• {admin_id}" for admin_id in ADMIN_USER_IDS)
        await update.message.reply_text(f"👑 Администраторы ({len(ADMIN_USER_IDS)}):\n{admins_list}")
    else:
        await update.message.reply_text("📭 Список администраторов пуст.")

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик команды /help"""
    help_text = (
        "📋 Доступные команды:\n"
        "/players - список игроков онлайн (доступно всем)\n"
        "/status - статус сервера (доступно всем)\n\n"
        
        "👑 Команды для администраторов (только в ЛС):\n"
        "/start_server - запустить сервер\n"
        "/stop_server - остановить сервер\n"
        "/restart_server - перезагрузить сервер\n"
        "/add_admin <id> - добавить администратора\n"
        "/del_admin <id> - удалить администратора\n"
        "/list_admins - список администраторов"
    )
    await update.message.reply_text(help_text)

async def ping_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Проверка работы бота"""
    await update.message.reply_text("🏓 Понг! Бот работает.")

def main():
    """Запуск бота"""
    # Загружаем список администраторов
    load_admin_ids()
    
    # Создаем Application
    application = Application.builder().token(TELEGRAM_TOKEN).build()
    
    # Добавляем обработчики команд
    application.add_handler(CommandHandler("start", start_command))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("ping", ping_command))
    application.add_handler(CommandHandler("players", players_command))
    application.add_handler(CommandHandler("status", status_command))
    application.add_handler(CommandHandler("start_server", start_server_command))
    application.add_handler(CommandHandler("stop_server", stop_server_command))
    application.add_handler(CommandHandler("restart_server", restart_server_command))
    application.add_handler(CommandHandler("add_admin", add_admin_command))
    application.add_handler(CommandHandler("del_admin", del_admin_command))
    application.add_handler(CommandHandler("list_admins", list_admins_command))
    
    # Запускаем бота
    logger.info("Бот запускается...")
    application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == '__main__':
    main()
