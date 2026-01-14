# !/usr/bin/env python3
import asyncio
import logging
import os
import re
from datetime import datetime, timedelta
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    ContextTypes
)
from core.config import TELEGRAM_TOKEN, TIMEWEB_TOKEN, MINECRAFT_SERVER_ID, MINECRAFT_SERVER_SSH
from core.server.facade import ServerFacade
from core.domain.model.action_result import ActionResult
from core.domain.model.server_status import ServerStatus
from core.domain.model.server_state import ServerState
from core.api.regru import RegRuClient

reg_ru_api = RegRuClient(TIMEWEB_TOKEN, MINECRAFT_SERVER_ID)
facade = ServerFacade(reg_ru_api)

ADMIN_IDS_FILE = "/root/minecraft-bot/78120051.txt"

# ==================== НАСТРОЙКИ УВЕДОМЛЕНИЙ ====================
ENABLE_ADMIN_NOTIFICATIONS = False  # ✅ Включить/выключить уведомления админам
ENABLE_GROUP_NOTIFICATIONS = False  # ✅ Включить/выключить уведомления в группу
NOTIFICATION_GROUP_ID = None  # ✅ ID группы для уведомлений (например: -1001234567890)

# Глобальные переменные
ADMIN_USER_IDS = set()

# ==================== IDLE SHUTDOWN СИСТЕМА ====================
IDLE_SHUTDOWN_TIMEOUT = 300  # 5 минут в секундах
CHECK_INTERVAL = 60  # Проверка каждую минуту

idle_since: datetime | None = None
idle_monitoring_active = False
idle_monitoring_enabled = True  # ✅ Флаг включения/выключения автовыключения
monitoring_task = None
bot_application = None  # ✅ Глобальная ссылка на Application

# Настройка логирования
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)

console_handler = logging.StreamHandler()
console_handler.setLevel(logging.DEBUG)
formatter = logging.Formatter(
    "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
console_handler.setFormatter(formatter)
logger.addHandler(console_handler)


def load_admin_ids():
    """Загружает список администраторов из файла"""
    global ADMIN_USER_IDS
    try:
        if os.path.exists(ADMIN_IDS_FILE):
            with open(ADMIN_IDS_FILE, 'r') as f:
                ADMIN_USER_IDS = set(int(line.strip()) for line in f if line.strip())
        else:
            with open(ADMIN_IDS_FILE, 'w') as f:
                pass
    except Exception as e:
        logger.error(f"Ошибка загрузки admin IDs: {e}")


def save_admin_ids():
    """Сохраняет список администраторов в файле"""
    try:
        with open(ADMIN_IDS_FILE, 'w') as f:
            for admin_id in ADMIN_USER_IDS:
                f.write(f"{admin_id}\n")
    except Exception as e:
        logger.error(f"Ошибка сохранения admin IDs: {e}")


def is_admin(user_id: int) -> bool:
    """Проверяет, является ли пользователь администратором"""
    return user_id == 78120051 or user_id in ADMIN_USER_IDS


# ==================== УВЕДОМЛЕНИЯ ====================

async def notify_admins(text: str):
    """Отправляет уведомления всем админам"""
    if not ENABLE_ADMIN_NOTIFICATIONS or not bot_application:
        return

    for admin_id in ADMIN_USER_IDS | {78120051}:
        try:
            await bot_application.bot.send_message(
                chat_id=admin_id,
                text=text,
                parse_mode="HTML"
            )
        except Exception as e:
            logger.error(f"Не удалось уведомить админа {admin_id}: {e}")


async def notify_group(text: str):
    """Отправляет уведомление в группу"""
    if not ENABLE_GROUP_NOTIFICATIONS or not NOTIFICATION_GROUP_ID or not bot_application:
        return

    try:
        await bot_application.bot.send_message(
            chat_id=NOTIFICATION_GROUP_ID,
            text=text,
            parse_mode="HTML"
        )
    except Exception as e:
        logger.error(f"Не удалось отправить уведомление в группу {NOTIFICATION_GROUP_ID}: {e}")


# ==================== МОНИТОРИНГ ПРОСТОЯ ====================

async def idle_monitor_loop():
    """
    Фоновая задача, проверяющая количество игроков.
    Запускает таймер выключения при 0 игроков.
    """
    global idle_since, idle_monitoring_active

    logger.info("🔍 Мониторинг простоя запущен")

    while idle_monitoring_active:
        try:
            # Пропускаем, если автовыключение отключено
            if not idle_monitoring_enabled:
                logger.debug("⏸️ Автовыключение отключено, мониторинг пропущен")
                idle_since = None
                await asyncio.sleep(CHECK_INTERVAL)
                continue

            # Получаем статус сервера
            status: ServerStatus = await facade.status()

            # Проверяем только если сервер в состоянии READY
            if status.state != ServerState.READY:
                logger.debug(f"Сервер не готов ({status.state}), мониторинг пропущен")
                idle_since = None
                await asyncio.sleep(CHECK_INTERVAL)
                continue

            players = status.players
            logger.info(f"👥 Игроков онлайн: {players}")

            # Логика таймера
            if players == 0:
                if idle_since is None:
                    # Начало простоя
                    idle_since = datetime.now()
                    logger.warning(f"⏱️ Таймер простоя запущен: {idle_since.strftime('%H:%M:%S')}")
                else:
                    # Проверяем, прошло ли 5 минут
                    elapsed = (datetime.now() - idle_since).total_seconds()
                    remaining = IDLE_SHUTDOWN_TIMEOUT - elapsed

                    logger.info(f"⏳ Простой {int(elapsed)}с / {IDLE_SHUTDOWN_TIMEOUT}с (осталось: {int(remaining)}с)")

                    if elapsed >= IDLE_SHUTDOWN_TIMEOUT:
                        logger.warning("🛑 Запуск автоматического выключения сервера")
                        await auto_shutdown_server()
                        idle_since = None
                        break  # Выходим из цикла после выключения
            else:
                # Игроки есть — сбрасываем таймер
                if idle_since is not None:
                    logger.info(f"✅ Игроки вернулись, таймер сброшен")
                idle_since = None

        except Exception as e:
            logger.error(f"❌ Ошибка в мониторинге: {e}")

        await asyncio.sleep(CHECK_INTERVAL)

    logger.info("🔍 Мониторинг простоя остановлен")


async def auto_shutdown_server():
    """
    Автоматическое выключение сервера с уведомлениями
    """
    global idle_monitoring_active

    logger.info("💾 Выполняю save-all и остановку сервера")

    # Уведомления админам
    await notify_admins(
        "⚠️ <b>Автоматическое выключение</b>\n\n"
        "Сервер был пуст 5 минут.\n"
        "Выполняю сохранение и остановку..."
    )

    # Останавливаем сервер через facade
    try:
        result: ActionResult = await facade.stop()

        if result.status == "locked":
            logger.error("❌ Сервер заблокирован, не удалось остановить")
            await notify_admins("❌ Не удалось остановить сервер (заблокирован)")
            return

        # Ждём остановки
        for _ in range(30):
            status: ServerStatus = await facade.status()
            if status.state == ServerState.OFF:
                logger.info("✅ Сервер успешно остановлен")
                break
            await asyncio.sleep(10)

        # Уведомления о результате
        await notify_admins("✅ Сервер успешно остановлен (автоматически)")
        await notify_group(
            "🛑 <b>Сервер Minecraft остановлен</b>\n\n"
            "Причина: отсутствие игроков 5 минут"
        )

        # Останавливаем мониторинг
        idle_monitoring_active = False

    except Exception as e:
        logger.error(f"❌ Ошибка при остановке сервера: {e}")
        await notify_admins(f"❌ Ошибка при остановке: {e}")


def start_idle_monitoring():
    """Запускает фоновый мониторинг"""
    global idle_monitoring_active, monitoring_task

    if not idle_monitoring_active:
        idle_monitoring_active = True
        monitoring_task = asyncio.create_task(idle_monitor_loop())
        logger.info("✅ Мониторинг простоя активирован")


def stop_idle_monitoring():
    """Останавливает фоновый мониторинг"""
    global idle_monitoring_active, idle_since

    idle_monitoring_active = False
    idle_since = None
    logger.info("🛑 Мониторинг простоя деактивирован")


def toggle_auto_shutdown() -> bool:
    """Переключает режим автовыключения"""
    global idle_monitoring_enabled, idle_since

    idle_monitoring_enabled = not idle_monitoring_enabled

    if not idle_monitoring_enabled:
        idle_since = None  # Сбрасываем таймер при отключении

    logger.info(f"🔄 Автовыключение {'включено' if idle_monitoring_enabled else 'отключено'}")
    return idle_monitoring_enabled


# ==================== КЛАВИАТУРЫ ====================

def get_control_keyboard(show_admin_buttons: bool = False) -> InlineKeyboardMarkup:
    """Создает клавиатуру с кнопками управления сервером"""
    keyboard = [
        [
            InlineKeyboardButton("📊 Статус", callback_data="status"),
            InlineKeyboardButton("💵 Пополнить", url="https://www.tbank.ru/cf/2dzkoyJFsJc")
        ]
    ]

    if show_admin_buttons:
        keyboard.append([
            InlineKeyboardButton("▶️ Запустить", callback_data="start_server"),
            InlineKeyboardButton("⏹️ Остановить", callback_data="stop_server")
        ])
        keyboard.append([
            InlineKeyboardButton("🔄 Перезагрузить", callback_data="restart_server")
        ])
        keyboard.append([
            InlineKeyboardButton("⚙️ Настройки", callback_data="settings")
        ])

    return InlineKeyboardMarkup(keyboard)


def get_settings_keyboard() -> InlineKeyboardMarkup:
    """Клавиатура настроек"""
    auto_status = "🟢 ВКЛ" if idle_monitoring_enabled else "🔴 ВЫКЛ"

    keyboard = [
        [InlineKeyboardButton(
            f"⏱️ Автовыключение: {auto_status}",
            callback_data="toggle_auto_shutdown"
        )],
        [InlineKeyboardButton("◀️ Назад", callback_data="back_to_main")]
    ]

    return InlineKeyboardMarkup(keyboard)


# ==================== КОМАНДЫ БОТА ====================

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
    status_msg = await update.message.reply_text(
        "⏳ Проверяю статус сервера...",
        parse_mode="HTML",
        disable_web_page_preview=True
    )

    try:
        status: ServerStatus = await facade.status()
    except Exception as e:
        await status_msg.edit_text(
            f"❌ Ошибка при получении статуса: {e}",
            parse_mode="HTML",
            disable_web_page_preview=True
        )
        return

    if status.state != ServerState.READY:
        text = ServerStatus.format_server_status(status)
        await status_msg.edit_text(
            f"{text}\n🎮 Minecraft: не запущен",
            parse_mode="HTML",
            disable_web_page_preview=True
        )
        return

    text = ServerStatus.format_players(status)
    await status_msg.edit_text(text, parse_mode="HTML", disable_web_page_preview=True)


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

    logger.info(f"Пользователь {user.id} запустил команду /start_server")

    msg = await update.message.reply_text(
        "▶️ Запускаю сервер в облаке...",
        reply_markup=get_control_keyboard(True)
    )

    action_result: ActionResult = await facade.start()

    if action_result.status == "locked":
        await msg.edit_text(
            "⚠️ Сервер уже выполняет другую операцию. Попробуйте позже.",
            reply_markup=get_control_keyboard(True),
            parse_mode="HTML",
            disable_web_page_preview=True
        )
        return

    total_wait = 0
    while total_wait < 300:
        status: ServerStatus = await facade.status()

        if status.state == ServerState.READY.value:
            logger.info("Minecraft сервер готов к игре")
            # ✅ Запускаем мониторинг при готовности
            start_idle_monitoring()
            # ✅ Уведомления
            await notify_group(
                "✅ <b>Сервер Minecraft запущен</b>\n\n"
                f"IP: <code>{status.ip}</code>\n"
                f"Игроков: {status.players}/{status.max_players}"
            )
            break

        if status.state == ServerState.BOOTING.value:
            await msg.edit_text(
                "⏳ VPS включен, Minecraft загружается...",
                reply_markup=get_control_keyboard(True),
                parse_mode="HTML",
                disable_web_page_preview=True
            )

        elif status.state == ServerState.STARTING.value:
            await msg.edit_text(
                "☁️ VPS запускается...",
                reply_markup=get_control_keyboard(True),
                parse_mode="HTML",
                disable_web_page_preview=True
            )

        await asyncio.sleep(10)
        total_wait += 10

    final_status: ServerStatus = await facade.status()
    text = ServerStatus.format_server_status(final_status)
    await msg.edit_text(
        text,
        reply_markup=get_control_keyboard(True),
        parse_mode="HTML",
        disable_web_page_preview=True
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

    # ✅ Останавливаем мониторинг
    stop_idle_monitoring()

    msg = await update.message.reply_text(
        "⏹️ Останавливаю сервер...",
        reply_markup=get_control_keyboard(True)
    )

    result: ActionResult = await facade.stop()

    if result.status == "locked":
        await msg.edit_text(
            "⚠️ Сервер уже выполняет другую операцию. Попробуйте позже.",
            reply_markup=get_control_keyboard(True)
        )
        return

    for _ in range(30):
        status: ServerStatus = await facade.status()
        if status.state == ServerState.OFF:
            break
        await asyncio.sleep(10)

    final_status: ServerStatus = await facade.status()
    text = ServerStatus.format_server_status(final_status)
    await msg.edit_text(
        text,
        reply_markup=get_control_keyboard(True),
        parse_mode="HTML",
        disable_web_page_preview=True
    )

    # ✅ Уведомления
    await notify_group("🛑 <b>Сервер Minecraft остановлен</b>\n\nПричина: остановка администратором")


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

    # ✅ Останавливаем мониторинг на время перезагрузки
    stop_idle_monitoring()

    msg = await update.message.reply_text(
        "🔄 Перезагрузка сервера...",
        reply_markup=get_control_keyboard(True)
    )

    result: ActionResult = await facade.reboot()

    text = ServerStatus.format_server_status(ServerStatus(state=ServerState.STARTING))
    await msg.edit_text(
        f"⏳ Сервер поставлен в очередь на перезагрузку\n{text}",
        reply_markup=get_control_keyboard(True)
    )

    if result.status != "locked":
        for _ in range(30):
            status: ServerStatus = await facade.status()
            if status.state == ServerState.READY:
                # ✅ Запускаем мониторинг после перезагрузки
                start_idle_monitoring()
                break
            await asyncio.sleep(10)

        final_status: ServerStatus = await facade.status()
        text = ServerStatus.format_server_status(final_status)
        await msg.edit_text(
            f"📊 Статус после перезагрузки:\n{text}",
            reply_markup=get_control_keyboard(True),
            parse_mode="HTML",
            disable_web_page_preview=True
        )

        # ✅ Уведомления
        await notify_group("🔄 <b>Сервер Minecraft перезагружен</b>")
    else:
        await msg.edit_text(
            "⚠️ Сервер уже выполняет другую операцию. Попробуйте позже.",
            reply_markup=get_control_keyboard(True),
            parse_mode="HTML",
            disable_web_page_preview=True
        )


async def status_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    show_admin = is_admin(user.id) and update.effective_chat.type == "private"

    msg = await update.message.reply_text("⏳ Проверяю статус...", reply_markup=get_control_keyboard(show_admin))

    result = await facade.status()
    text = ServerStatus.format_server_status(result)

    await msg.edit_text(
        text,
        reply_markup=get_control_keyboard(show_admin),
        parse_mode="HTML",
        disable_web_page_preview=True
    )


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


# ==================== ОБРАБОТЧИК КНОПОК ====================

async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик нажатий на inline кнопки"""
    query = update.callback_query
    await query.answer()

    user = update.effective_user
    show_admin = is_admin(user.id) and update.effective_chat.type == "private"

    data = query.data

    # ========== СТАТУС ==========
    if data == "status":
        await query.edit_message_text("⏳ Проверяю статус...")
        result: ServerStatus = await facade.status()
        text = ServerStatus.format_server_status(result)
        await query.edit_message_text(
            text,
            reply_markup=get_control_keyboard(show_admin),
            parse_mode="HTML",
            disable_web_page_preview=True
        )

    # ========== НАСТРОЙКИ ==========
    elif data == "settings":
        if not show_admin:
            await query.edit_message_text("❌ У вас нет прав для выполнения этой команды.")
            return

        auto_status = "🟢 Включено" if idle_monitoring_enabled else "🔴 Отключено"
        settings_text = (
            "⚙️ <b>Настройки сервера</b>\n\n"
            f"⏱️ <b>Автовыключение:</b> {auto_status}\n"
            f"<i>Сервер выключается через {IDLE_SHUTDOWN_TIMEOUT // 60} мин. при 0 игроков</i>\n\n"
            "Используйте кнопки ниже для изменения настроек:"
        )
        await query.edit_message_text(
            settings_text,
            reply_markup=get_settings_keyboard(),
            parse_mode="HTML"
        )

    # ========== ПЕРЕКЛЮЧЕНИЕ АВТОВЫКЛЮЧЕНИЯ ==========
    elif data == "toggle_auto_shutdown":
        if not show_admin:
            await query.answer("❌ У вас нет прав", show_alert=True)
            return

        new_state = toggle_auto_shutdown()
        status_emoji = "🟢" if new_state else "🔴"
        status_text = "включено" if new_state else "отключено"

        await query.answer(f"{status_emoji} Автовыключение {status_text}", show_alert=True)

        # Обновляем меню настроек
        auto_status = "🟢 Включено" if new_state else "🔴 Отключено"
        settings_text = (
            "⚙️ <b>Настройки сервера</b>\n\n"
            f"⏱️ <b>Автовыключение:</b> {auto_status}\n"
            f"<i>Сервер выключается через {IDLE_SHUTDOWN_TIMEOUT // 60} мин. при 0 игроков</i>\n\n"
            "Используйте кнопки ниже для изменения настроек:"
        )
        await query.edit_message_text(
            settings_text,
            reply_markup=get_settings_keyboard(),
            parse_mode="HTML"
        )

    # ========== НАЗАД ==========
    elif data == "back_to_main":
        result: ServerStatus = await facade.status()
        text = ServerStatus.format_server_status(result)
        await query.edit_message_text(
            text,
            reply_markup=get_control_keyboard(show_admin),
            parse_mode="HTML",
            disable_web_page_preview=True
        )

    # ========== ЗАПУСК СЕРВЕРА ==========
    elif data == "start_server":
        if not show_admin:
            await query.edit_message_text("❌ У вас нет прав для выполнения этой команды.")
            return

        await query.edit_message_text("▶️ Запускаю сервер...")
        action_result: ActionResult = await facade.start()

        if action_result.status == "locked":
            await query.edit_message_text(
                "⚠️ Сервер уже выполняет другую операцию. Попробуйте позже.",
                reply_markup=get_control_keyboard(True)
            )
            return

        for _ in range(30):
            status: ServerStatus = await facade.status()
            if status.state == ServerState.READY:
                start_idle_monitoring()
                await notify_group(
                    "✅ <b>Сервер Minecraft запущен</b>\n\n"
                    f"IP: <code>{status.ip}</code>\n"
                    f"Игроков: {status.players}/{status.max_players}"
                )
                break
            await asyncio.sleep(10)

        final_status: ServerStatus = await facade.status()
        text = ServerStatus.format_server_status(final_status)
        await query.edit_message_text(text, reply_markup=get_control_keyboard(True))

    # ========== ОСТАНОВКА СЕРВЕРА ==========
    elif data == "stop_server":
        if not show_admin:
            await query.edit_message_text("❌ У вас нет прав для выполнения этой команды.")
            return

        stop_idle_monitoring()

        await query.edit_message_text("⏹️ Останавливаю сервер...")
        result: ActionResult = await facade.stop()

        if result.status == "locked":
            await query.edit_message_text(
                "⚠️ Сервер уже выполняет другую операцию. Попробуйте позже.",
                reply_markup=get_control_keyboard(True)
            )
            return

        for _ in range(30):
            status: ServerStatus = await facade.status()
            if status.state == ServerState.OFF:
                break
            await asyncio.sleep(10)

        final_status: ServerStatus = await facade.status()
        text = ServerStatus.format_server_status(final_status)
        await query.edit_message_text(text, reply_markup=get_control_keyboard(True))

        await notify_group("🛑 <b>Сервер Minecraft остановлен</b>\n\nПричина: остановка администратором")

    # ========== ПЕРЕЗАГРУЗКА СЕРВЕРА ==========
    elif data == "restart_server":
        if not show_admin:
            await query.edit_message_text("❌ У вас нет прав для выполнения этой команды.")
            return

        stop_idle_monitoring()

        await query.edit_message_text("🔄 Перезагружаю сервер...")
        result: ActionResult = await facade.reboot()

        if result.status == "locked":
            await query.edit_message_text(
                "⚠️ Сервер уже выполняет другую операцию. Попробуйте позже.",
                reply_markup=get_control_keyboard(True)
            )
            return

        for _ in range(30):
            status: ServerStatus = await facade.status()
            if status.state == ServerState.READY:
                start_idle_monitoring()
                break
            await asyncio.sleep(10)

        final_status: ServerStatus = await facade.status()
        text = ServerStatus.format_server_status(final_status)
        await query.edit_message_text(text, reply_markup=get_control_keyboard(True))

        await notify_group("🔄 <b>Сервер Minecraft перезагружен</b>")


def main():
    """Запуск бота"""
    global bot_application

    load_admin_ids()

    application = Application.builder().token(TELEGRAM_TOKEN).build()
    bot_application = application  # ✅ Сохраняем глобальную ссылку

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

    application.add_handler(CallbackQueryHandler(button_callback))

    logger.info("Бот запускается...")
    application.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == '__main__':
    main()