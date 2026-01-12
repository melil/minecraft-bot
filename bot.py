#!/usr/bin/env python3
import asyncio
import logging
import os
import re
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    ContextTypes
)
from server_monitor import ServerMonitor
from core.config import TELEGRAM_TOKEN, TIMEWEB_TOKEN, MINECRAFT_SERVER_ID, MINECRAFT_SERVER_SSH
from core.server.facade import ServerFacade
from core.domain.model.action_result import ActionResult
from core.domain.model.server_status import ServerStatus
from core.domain.model.server_state import ServerState
from core.api.regru import RegRuClient

reg_ru_api = RegRuClient(TIMEWEB_TOKEN, MINECRAFT_SERVER_ID)
facade = ServerFacade(reg_ru_api)
monitor = ServerMonitor()

ADMIN_IDS_FILE = "/root/minecraft-bot/admins.txt"

# Глобальные переменные
ADMIN_USER_IDS = set()

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
    keyboard = [[InlineKeyboardButton("📊 Статус", callback_data="status")]]
    
    # Кнопка статуса (доступна всем)

    # Кнопки администратора (только для админов)
    if show_admin_buttons:
        keyboard.append([
            InlineKeyboardButton("▶️ Запустить", callback_data="start_server"),
            InlineKeyboardButton("⏹️ Остановить", callback_data="stop_server")
        ])
        keyboard.append([InlineKeyboardButton("🔄 Перезагрузить", callback_data="restart_server")])
    
    return InlineKeyboardMarkup(keyboard)

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
    """Обработчик команды /players (доступна всем)"""
    status_msg = await update.message.reply_text("⏳ Проверяю статус сервера...")

    try:
        status: ServerStatus = await facade.status()
    except Exception as e:
        await status_msg.edit_text(f"❌ Ошибка при получении статуса: {e}")
        return

    # Если Minecraft не активен
    if not status.state.BOOTING:
        text = ServerStatus.format_server_status(status)
        await status_msg.edit_text(f"{text}\n🎮 Minecraft: не запущен")
        return

    # Если Minecraft активен
    text =  ServerStatus.format_server_status(status)
    await status_msg.edit_text(text)


async def start_server_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик команды /start_server (только для админов в ЛС)"""
    chat = update.effective_chat
    user = update.effective_user

    if chat.type != "private":
        await update.message.reply_text("⚠️ Эта команда доступна только в личных сообщениях.")
        return

    if not is_admin(user.id):
        await update.message.reply_text("❌ У вас нет прав для выполнения этой команды.")
        return

    # Шаг 1 — ставим VPS в очередь на включение через фасад
    msg = await update.message.reply_text(
        "▶️ Запускаю сервер в облаке...",
        reply_markup=get_control_keyboard(True)
    )

    action_result: ActionResult = await facade.start()

    # Если операция заблокирована
    if action_result.status == "locked":
        await msg.edit_text(
            "⚠️ Сервер уже выполняет другую операцию. Попробуйте позже.",
            reply_markup=get_control_keyboard(True)
        )
        return

    # Шаг 2 — ждём, пока VPS поднимется и Minecraft станет готов
    total_wait = 0
    while total_wait < 300:  # максимум 5 минут
        status: ServerStatus = await facade.status()

        # Minecraft готов
        if status.state == ServerState.READY.value:
            break

        # VPS включен, Minecraft грузится
        if status.state == ServerState.BOOTING.value:
            await msg.edit_text(
                "⏳ VPS включен, Minecraft загружается...",
                reply_markup=get_control_keyboard(True)
            )

        # VPS всё ещё включается
        elif status.state == ServerState.STARTING.value:
            await msg.edit_text(
                "☁️ VPS запускается...",
                reply_markup=get_control_keyboard(True)
            )

        await asyncio.sleep(10)
        total_wait += 10

    # Шаг 3 — финальный статус
    final_status: ServerStatus = await facade.status()
    text = ServerStatus.format_server_status(final_status)
    await msg.edit_text(
        text,
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

    # Шаг 1 — ставим VPS в очередь на остановку через фасад
    msg = await update.message.reply_text(
        "⏹️ Останавливаю сервер...",
        reply_markup=get_control_keyboard(True)
    )

    result: ActionResult = await facade.stop()

    # Шаг 2 — если операция заблокирована
    if result.status == "locked":
        await msg.edit_text(
            "⚠️ Сервер уже выполняет другую операцию. Попробуйте позже.",
            reply_markup=get_control_keyboard(True)
        )
        return

    # Шаг 3 — ждём, пока VPS остановится
    for _ in range(30):  # максимум ~5 минут ожидания
        status: ServerStatus = await facade.status()
        if status.state == ServerState.OFF:
            break
        await asyncio.sleep(10)

    # Шаг 4 — финальный статус
    final_status: ServerStatus = await facade.status()
    text = ServerStatus.format_server_status(final_status)
    await msg.edit_text(
        text,
        reply_markup=get_control_keyboard(True)
    )


async def restart_server_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик команды /restart_server (только для админов в ЛС)"""
    chat = update.effective_chat
    user = update.effective_user

    if chat.type != "private":
        await update.message.reply_text(
            "⚠️ Эта команда доступна только в личных сообщениях."
        )
        return

    if not is_admin(user.id):
        await update.message.reply_text("❌ У вас нет прав для выполнения этой команды.")
        return

    # Шаг 1 — отправляем в очередь перезагрузки через фасад
    msg = await update.message.reply_text(
        "🔄 Перезагрузка сервера...",
        reply_markup=get_control_keyboard(True)
    )

    result: ActionResult = await facade.reboot()  # <-- теперь через facade

    # Шаг 2 — информируем пользователя о статусе очереди
    text = ServerStatus.format_server_status(ServerStatus(
        state=ServerState.STARTING
    ))
    await msg.edit_text(f"⏳ Сервер поставлен в очередь на перезагрузку\n{text}",
                        reply_markup=get_control_keyboard(True))

    # Шаг 3 — ждём, пока Minecraft будет готов
    if result.status != "locked":
        # Ожидаем готовности Minecraft (booting → ready)
        for _ in range(30):  # максимум ~5 минут (30*10s)
            status: ServerStatus = await facade.status()
            if status.state == ServerState.READY:
                break
            await asyncio.sleep(10)

        # Шаг 4 — выводим финальный статус
        final_status: ServerStatus = await facade.status()
        text = ServerStatus.format_server_status(final_status)
        await update.message.reply_text(
            f"📊 Статус после перезагрузки:\n{text}",
            reply_markup=get_control_keyboard(True)
        )
    else:
        # Если операция заблокирована
        await msg.edit_text(
            "⚠️ Сервер уже выполняет другую операцию. Попробуйте позже.",
            reply_markup=get_control_keyboard(True)
        )

async def status_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    show_admin = is_admin(user.id) and update.effective_chat.type == "private"

    msg = await update.message.reply_text("⏳ Проверяю статус...", reply_markup=get_control_keyboard(show_admin))

    result = await facade.status()
    text = ServerStatus.format_server_status(result)

    await msg.edit_text(text, reply_markup=get_control_keyboard(show_admin))



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
    
    # Создаем Application with post_init callback
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
    
    # Добавляем обработчик callback query для inline кнопок
    #application.add_handler(CallbackQueryHandler(button_callback))
    
    # Запускаем бота
    logger.info("Бот запускается...")
    application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == '__main__':
    main()
