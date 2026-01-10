#!/usr/bin/env python3
import asyncio
import logging
import subprocess
import os
import re
from typing import Set
import aiohttp
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    filters,
    ContextTypes
)
from server_monitor import ServerMonitor
from config import TELEGRAM_TOKEN, TIMEWEB_TOKEN, SERVER_ID, SERVER_B_IP, SERVER_B_SSH

ADMIN_IDS_FILE = "/root/minecraft-bot/admins.txt"

# Глобальные переменные
ADMIN_USER_IDS = set()

monitor = ServerMonitor()

# Idle shutdown monitoring
IDLE_SHUTDOWN_TIMEOUT = 300  # 5 minutes in seconds
idle_since = None  # Timestamp when players hit 0
idle_monitoring_active = False

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

def get_control_keyboard(show_admin_buttons: bool = False) -> InlineKeyboardMarkup:
    """Создает клавиатуру с кнопками управления сервером"""
    keyboard = []
    
    # Кнопка статуса (доступна всем)
    keyboard.append([InlineKeyboardButton("📊 Статус", callback_data="status")])
    
    # Кнопки администратора (только для админов)
    if show_admin_buttons:
        keyboard.append([
            InlineKeyboardButton("▶️ Запустить", callback_data="start_server"),
            InlineKeyboardButton("⏹️ Остановить", callback_data="stop_server")
        ])
        keyboard.append([InlineKeyboardButton("🔄 Перезагрузить", callback_data="restart_server")])
    
    return InlineKeyboardMarkup(keyboard)

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

async def get_player_count() -> int:
    """Returns the number of players online, or -1 if server is unavailable"""
    try:
        players_output = await execute_ssh_command("/root/scripts/players.sh")
        if not players_output or "❌" in players_output:
            return -1
        
        # Parse player count from output
        match = re.search(r'There are (\d+) of a max of (\d+)', players_output)
        if match:
            return int(match.group(1))
        
        # Check for "There are 0" format
        if "There are 0" in players_output:
            return 0
        
        return -1
    except Exception as e:
        logger.error(f"Error getting player count: {e}")
        return -1

async def save_world_and_shutdown():
    """Saves the world and shuts down the VPS"""
    try:
        logger.info("Starting idle shutdown: saving world and shutting down VPS")
        result = await execute_ssh_command("/root/scripts/stop_server_manually.sh")
        logger.info(f"Idle shutdown result: {result}")
        return result
    except Exception as e:
        logger.error(f"Error during idle shutdown: {e}")
        return f"Error: {str(e)}"

async def idle_shutdown_monitor(context: ContextTypes.DEFAULT_TYPE):
    """Background task that monitors player count and shuts down server if idle"""
    global idle_since, idle_monitoring_active
    
    if not idle_monitoring_active:
        return
    
    try:
        # Check if server is available
        if not await monitor.ssh_available():
            idle_since = None
            return
        
        if not await monitor.minecraft_ready():
            idle_since = None
            return
        
        player_count = await get_player_count()
        
        if player_count == -1:
            # Server unavailable or error
            idle_since = None
            return
        
        current_time = asyncio.get_event_loop().time()
        
        if player_count > 0:
            # Players are online, reset idle timer
            idle_since = None
            logger.debug(f"Players online: {player_count}, resetting idle timer")
        else:
            # No players online
            if idle_since is None:
                # First time we see 0 players, start timer
                idle_since = current_time
                logger.info("Server is now empty, starting idle shutdown timer")
            else:
                # Check if timeout reached
                idle_duration = current_time - idle_since
                if idle_duration >= IDLE_SHUTDOWN_TIMEOUT:
                    logger.info(f"Idle timeout reached ({IDLE_SHUTDOWN_TIMEOUT}s), shutting down server")
                    idle_monitoring_active = False
                    await save_world_and_shutdown()
                else:
                    remaining = IDLE_SHUTDOWN_TIMEOUT - idle_duration
                    logger.debug(f"Server idle for {int(idle_duration)}s, {int(remaining)}s until shutdown")
    except Exception as e:
        logger.error(f"Error in idle shutdown monitor: {e}")

async def start_idle_monitoring(application):
    """Starts the idle monitoring background task"""
    global idle_monitoring_active
    idle_monitoring_active = True
    
    while idle_monitoring_active:
        try:
            # Run monitoring check
            await idle_shutdown_monitor(None)
            # Check every 30 seconds
            await asyncio.sleep(30)
        except Exception as e:
            logger.error(f"Error in idle monitoring loop: {e}")
            await asyncio.sleep(30)

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
        show_admin = is_admin(user.id)
        welcome_text = (
            "👋 Привет! Я бот для управления Minecraft сервером.\n\n"
            "📋 Доступные команды:\n"
            "/status - статус сервера\n"
            "/players - список игроков онлайн\n"
        )
        if show_admin:
            welcome_text += (
                "/start_server - запустить сервер\n"
                "/stop_server - остановить сервер\n"
                "/restart_server - перезагрузить сервер\n\n"
                "👑 Команды для администраторов:\n"
                "/add_admin <id> - добавить администратора\n"
                "/list_admins - список администраторов\n"
                "/del_admin <id> - удалить администратора\n"
            )
        welcome_text += "\n💡 Используйте кнопки ниже для быстрого управления:"
        await update.message.reply_text(welcome_text, reply_markup=get_control_keyboard(show_admin))
    else:
        await update.message.reply_text(
            "🤖 Бот Minecraft сервера активен.\n"
            "Используйте /players для проверки игроков онлайн.",
            reply_markup=get_control_keyboard(False)
        )

async def players_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик команды /players (доступна везде)"""
    status_msg = await update.message.reply_text("⏳ Проверяю игроков онлайн...")
    status = await check_server_status()
    await status_msg.edit_text(status)

async def start_server_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик команды /start_server"""
    global idle_since
    user = update.effective_user
    
    if update.effective_chat.type != "private":
        await update.message.reply_text("⚠️ Эта команда доступна только в личных сообщениях.")
        return

    if not is_admin(user.id):
        await update.message.reply_text("❌ Нет прав")
        return

    msg = await update.message.reply_text("☁️ Запускаю сервер в облаке...", reply_markup=get_control_keyboard(True))
    await start_server_via_api()

    await msg.edit_text("⏳ Жду пока Minecraft станет доступен...", reply_markup=get_control_keyboard(True))

    if await wait_until_playable(monitor):
        # Reset idle timer when server starts
        idle_since = None
        await msg.edit_text(
            "🎮 Minecraft сервер ГОТОВ!\n"
            "✅ Можно заходить и играть",
            reply_markup=get_control_keyboard(True)
        )
    else:
        await msg.edit_text(
            "⚠️ Сервер не стал доступен за 5 минут",
            reply_markup=get_control_keyboard(True)
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
    
    status_msg = await update.message.reply_text("⏳ Останавливаю Minecraft сервер...", reply_markup=get_control_keyboard(True))
    result = await execute_ssh_command("/root/scripts/stop_server_manually.sh")
    await status_msg.edit_text(result, reply_markup=get_control_keyboard(True))

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
    
    status_msg = await update.message.reply_text("⏳ Перезагружаю Minecraft сервер...", reply_markup=get_control_keyboard(True))
    result = await execute_ssh_command("/root/scripts/reboot_server_manually.sh")
    await status_msg.edit_text(result, reply_markup=get_control_keyboard(True))
    
    # Ждем и проверяем статус
    await asyncio.sleep(30)
    status = await check_server_status()
    await update.message.reply_text(f"📊 Статус после перезагрузки:\n{status}", reply_markup=get_control_keyboard(True))

async def status_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик команды /status"""
    user = update.effective_user
    show_admin = is_admin(user.id) and update.effective_chat.type == "private"
    
    msg = await update.message.reply_text("⏳ Проверяю статус...", reply_markup=get_control_keyboard(show_admin))
    status = await monitor.full_status()
    await msg.edit_text(status, reply_markup=get_control_keyboard(show_admin))

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

async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик нажатий на inline кнопки"""
    query = update.callback_query
    user = query.from_user
    chat = query.message.chat
    
    # Отвечаем на callback query, чтобы убрать индикатор загрузки
    await query.answer()
    
    callback_data = query.data
    show_admin = is_admin(user.id) and chat.type == "private"
    
    if callback_data == "status":
        # Обновляем сообщение со статусом
        await query.message.edit_text("⏳ Проверяю статус...", reply_markup=get_control_keyboard(show_admin))
        status = await monitor.full_status()
        await query.message.edit_text(status, reply_markup=get_control_keyboard(show_admin))
    
    elif callback_data == "start_server":
        # Проверка прав и типа чата
        if chat.type != "private":
            await query.answer("⚠️ Эта команда доступна только в личных сообщениях.", show_alert=True)
            return
        
        if not is_admin(user.id):
            await query.answer("❌ У вас нет прав для выполнения этой команды.", show_alert=True)
            return
        
        # Запуск сервера
        global idle_since
        await query.message.edit_text("☁️ Запускаю сервер в облаке...", reply_markup=get_control_keyboard(True))
        await start_server_via_api()
        await query.message.edit_text("⏳ Жду пока Minecraft станет доступен...", reply_markup=get_control_keyboard(True))
        
        if await wait_until_playable(monitor):
            idle_since = None
            await query.message.edit_text(
                "🎮 Minecraft сервер ГОТОВ!\n"
                "✅ Можно заходить и играть",
                reply_markup=get_control_keyboard(True)
            )
        else:
            await query.message.edit_text(
                "⚠️ Сервер не стал доступен за 5 минут",
                reply_markup=get_control_keyboard(True)
            )
    
    elif callback_data == "stop_server":
        # Проверка прав и типа чата
        if chat.type != "private":
            await query.answer("⚠️ Эта команда доступна только в личных сообщениях.", show_alert=True)
            return
        
        if not is_admin(user.id):
            await query.answer("❌ У вас нет прав для выполнения этой команды.", show_alert=True)
            return
        
        # Остановка сервера
        await query.message.edit_text("⏳ Останавливаю Minecraft сервер...", reply_markup=get_control_keyboard(True))
        result = await execute_ssh_command("/root/scripts/stop_server_manually.sh")
        await query.message.edit_text(result, reply_markup=get_control_keyboard(True))
    
    elif callback_data == "restart_server":
        # Проверка прав и типа чата
        if chat.type != "private":
            await query.answer("⚠️ Эта команда доступна только в личных сообщениях.", show_alert=True)
            return
        
        if not is_admin(user.id):
            await query.answer("❌ У вас нет прав для выполнения этой команды.", show_alert=True)
            return
        
        # Перезагрузка сервера
        await query.message.edit_text("⏳ Перезагружаю Minecraft сервер...", reply_markup=get_control_keyboard(True))
        result = await execute_ssh_command("/root/scripts/reboot_server_manually.sh")
        await query.message.edit_text(result, reply_markup=get_control_keyboard(True))
        
        # Ждем и проверяем статус
        await asyncio.sleep(30)
        status = await check_server_status()
        await query.message.reply_text(f"📊 Статус после перезагрузки:\n{status}", reply_markup=get_control_keyboard(True))

async def post_init(application: Application) -> None:
    """Callback that runs after application initialization to start background tasks"""
    asyncio.create_task(start_idle_monitoring(application))

def main():
    """Запуск бота"""
    # Загружаем список администраторов
    load_admin_ids()
    
    # Создаем Application with post_init callback
    application = Application.builder().token(TELEGRAM_TOKEN).post_init(post_init).build()
    
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
    
    # Добавляем обработчик callback query для inline кнопок
    application.add_handler(CallbackQueryHandler(button_callback))
    
    # Запускаем бота
    logger.info("Бот запускается...")
    application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == '__main__':
    main()
