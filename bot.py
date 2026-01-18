#!/usr/bin/env python3
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
from core.config import TELEGRAM_TOKEN, REGRU_CLOUD_TOKEN, MINECRAFT_SERVER_ID, MINECRAFT_SERVER_SSH
from core.server.facade import ServerFacade
from core.domain.model.action_result import ActionResult
from core.domain.model.server_status import ServerStatus
from core.domain.model.server_state import ServerState
from core.api.regru import RegRuClient

reg_ru_api = RegRuClient(REGRU_CLOUD_TOKEN, MINECRAFT_SERVER_ID)
facade = ServerFacade(reg_ru_api)

ADMIN_IDS_FILE = "/root/minecraft-bot/admins.txt"

# ==================== НАСТРОЙКИ УВЕДОМЛЕНИЙ ====================
ENABLE_ADMIN_NOTIFICATIONS = False  # ✅ Включить/выключить уведомления админам
ENABLE_GROUP_NOTIFICATIONS = True  # ✅ Включить/выключить уведомления в группу
NOTIFICATION_GROUP_ID = -5142213077  # ✅ ID группы для уведомлений (например: -1001234567890)

# Глобальные переменные
ADMIN_USER_IDS = set()

# ==================== IDLE SHUTDOWN СИСТЕМА ====================
IDLE_SHUTDOWN_TIMEOUT = 600  # 5 минут в секундах
CHECK_INTERVAL = 30  # Проверка каждую минуту

idle_since: datetime | None = None
idle_monitoring_active = False
idle_monitoring_enabled = True  # ✅ Флаг включения/выключения автовыключения
monitoring_task = None
bot_application = None  # ✅ Глобальная ссылка на Application

# ==================== БЛОКИРОВКА ОПЕРАЦИЙ ====================
active_operations = {}  # {chat_id: {task, operation_type, message_id}}

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
            logger.debug("📡 Получаю статус сервера...")
            status: ServerStatus = await facade.status()
            logger.debug(f"📊 Статус получен: state={status.state}, players={status.players}")

            # Проверяем только если сервер в состоянии READY
            if status.state != ServerState.READY:
                logger.debug(f"⏸️ Сервер не готов ({status.state}), мониторинг пропущен")
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
                    logger.info(f"✅ Игроки вернулись ({players}), таймер сброшен")
                idle_since = None

        except Exception as e:
            logger.error(f"❌ Ошибка в мониторинге: {e}", exc_info=True)

        logger.debug(f"💤 Сон {CHECK_INTERVAL}с...")
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


# ==================== УПРАВЛЕНИЕ ОПЕРАЦИЯМИ ====================

def is_operation_active(chat_id: int) -> bool:
    """Проверяет, активна ли операция для чата"""
    return chat_id in active_operations


def cancel_operation(chat_id: int):
    """Отменяет активную операцию"""
    if chat_id in active_operations:
        op = active_operations[chat_id]
        if 'task' in op and not op['task'].done():
            op['task'].cancel()
        del active_operations[chat_id]
        logger.info(f"Операция для чата {chat_id} отменена")


async def perform_server_operation(
        operation_type: str,
        chat_id: int,
        message_id: int,
        show_admin: bool
):
    """
    Фоновая задача для выполнения операций с сервером
    operation_type: 'start', 'stop', 'restart'
    """
    try:
        logger.info(f"Начало операции {operation_type} для чата {chat_id}")

        # Выполняем операцию
        if operation_type == "start":
            action_result = await facade.start()
            target_state = ServerState.READY
            success_message = "✅ Сервер успешно запущен!"
            group_notification = lambda status: (
                "✅ <b>Сервер Minecraft запущен</b>\n\n"
                f"IP: <code>{status.ip}</code>\n"
                f"Игроков: {status.players}/{status.max_players}"
            )

        elif operation_type == "stop":
            action_result = await facade.stop()
            target_state = ServerState.OFF
            success_message = "✅ Сервер успешно остановлен!"
            group_notification = lambda status: (
                "🛑 <b>Сервер Minecraft остановлен</b>\n\n"
                "Причина: остановка администратором"
            )

        elif operation_type == "restart":
            action_result = await facade.reboot()
            target_state = ServerState.READY
            success_message = "✅ Сервер успешно перезагружен!"
            group_notification = lambda status: "🔄 <b>Сервер Minecraft перезагружен</b>"

        else:
            logger.error(f"Неизвестный тип операции: {operation_type}")
            return

        # Проверяем, что операция не была отменена
        if chat_id not in active_operations:
            logger.info(f"Операция {operation_type} была отменена")
            return

        # Проверяем результат
        if action_result.status == "locked":
            await bot_application.bot.edit_message_text(
                chat_id=chat_id,
                message_id=message_id,
                text="⚠️ Сервер уже выполняет другую операцию. Попробуйте позже.",
                reply_markup=await get_dynamic_keyboard(show_admin),
                parse_mode="HTML"
            )
            cancel_operation(chat_id)
            return

        # Ожидание завершения
        max_attempts = 30
        for attempt in range(max_attempts):
            # Проверяем отмену
            if chat_id not in active_operations:
                logger.info(f"Операция {operation_type} была отменена на шаге {attempt}")
                return

            status = await facade.status()

            # Обновляем сообщение с прогрессом
            progress = f"⏳ {attempt + 1}/{max_attempts}"
            state_emoji = {
                ServerState.OFF: "⚫",
                ServerState.STARTING: "🟡",
                ServerState.BOOTING: "🟠",
                ServerState.READY: "🟢"
            }.get(status.state, "⚪")

            await bot_application.bot.edit_message_text(
                chat_id=chat_id,
                message_id=message_id,
                text=f"{state_emoji} {progress}\n\n{ServerStatus.format_server_status(status, monitoring_enabled=idle_monitoring_enabled)}",
                reply_markup=await get_dynamic_keyboard(show_admin),
                parse_mode="HTML",
                disable_web_page_preview=True
            )

            # Проверяем достижение целевого состояния
            if status.state == target_state:
                logger.info(f"Операция {operation_type} завершена успешно")

                # Управление мониторингом
                if operation_type == "start" or operation_type == "restart":
                    start_idle_monitoring()
                elif operation_type == "stop":
                    stop_idle_monitoring()

                # Финальное сообщение
                await bot_application.bot.edit_message_text(
                    chat_id=chat_id,
                    message_id=message_id,
                    text=f"{success_message}\n\n{ServerStatus.format_server_status(status, monitoring_enabled=idle_monitoring_enabled)}",
                    reply_markup=await get_dynamic_keyboard(show_admin),
                    parse_mode="HTML",
                    disable_web_page_preview=True
                )

                # Уведомления
                await notify_group(group_notification(status))

                break

            await asyncio.sleep(10)

        # Удаляем операцию из активных
        cancel_operation(chat_id)

    except asyncio.CancelledError:
        logger.info(f"Операция {operation_type} отменена пользователем")
        # Восстанавливаем кнопки
        try:
            await bot_application.bot.edit_message_text(
                chat_id=chat_id,
                message_id=message_id,
                text="❌ Операция отменена",
                reply_markup=await get_dynamic_keyboard(show_admin),
                parse_mode="HTML"
            )
        except:
            pass
    except Exception as e:
        logger.error(f"Ошибка в операции {operation_type}: {e}")
        cancel_operation(chat_id)
        try:
            await bot_application.bot.edit_message_text(
                chat_id=chat_id,
                message_id=message_id,
                text=f"❌ Ошибка: {e}",
                reply_markup=await get_dynamic_keyboard(show_admin),
                parse_mode="HTML"
            )
        except:
            pass


# ==================== КЛАВИАТУРЫ ====================

async def get_dynamic_keyboard(show_admin_buttons: bool = False) -> InlineKeyboardMarkup:
    """Создает динамическую клавиатуру в зависимости от состояния сервера"""
    keyboard = [
        [
            InlineKeyboardButton("📊 Статус", callback_data="status"),
            InlineKeyboardButton("💵 Пополнить", callback_data="popup_balance")
        ]
    ]

    if show_admin_buttons:
        try:
            # Получаем текущий статус сервера
            status: ServerStatus = await facade.status()

            # В зависимости от состояния показываем разные кнопки
            if status.state == ServerState.OFF:
                # Сервер выключен — только кнопка запуска
                keyboard.append([
                    InlineKeyboardButton("▶️ Запустить", callback_data="start_server")
                ])

            elif status.state in [ServerState.STARTING, ServerState.BOOTING]:
                # Сервер запускается — показываем состояние
                keyboard.append([
                    InlineKeyboardButton("⏳ Запускается...", callback_data="status")
                ])

            elif status.state == ServerState.READY:
                # Сервер работает — кнопки остановки и перезагрузки
                keyboard.append([
                    InlineKeyboardButton("⏹️ Остановить", callback_data="stop_server"),
                    InlineKeyboardButton("🔄 Перезагрузить", callback_data="restart_server")
                ])

            # Кнопка настроек всегда доступна
            keyboard.append([
                InlineKeyboardButton("⚙️ Настройки", callback_data="settings")
            ])

        except Exception as e:
            logger.error(f"Ошибка получения статуса для клавиатуры: {e}")
            # Фолбэк на стандартные кнопки
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


def get_popup_balance_keyboard() -> InlineKeyboardMarkup:
    """Клавиатура пополнения баланса"""
    keyboard = [
        [InlineKeyboardButton(
            f"🟨 Тиньков сбор:",
            url="https://www.tbank.ru/cf/2dzkoyJFsJc"
        ), InlineKeyboardButton(
            f"🟩 СБП, Карта и тд (моментально):",
            url="https://reg.cloud/prolong"
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
        keyboard = await get_dynamic_keyboard(show_admin)
        await update.message.reply_text(welcome_text, reply_markup=keyboard)
    else:
        keyboard = await get_dynamic_keyboard(False)
        await update.message.reply_text(
            "🤖 Бот Minecraft сервера активен.\n"
            "Используйте /players для проверки игроков онлайн.",
            reply_markup=keyboard
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
        text = ServerStatus.format_server_status(status, monitoring_enabled=idle_monitoring_enabled)
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

    # if chat.type != "private":
    #     await update.message.reply_text("⚠️ Эта команда доступна только в личных сообщениях.")
    #     return

    if not is_admin(user.id):
        await update.message.reply_text("❌ У вас нет прав для выполнения этой команды.")
        return

    # Проверяем активные операции
    if is_operation_active(chat.id):
        await update.message.reply_text("⚠️ Уже выполняется другая операция. Дождитесь завершения.")
        return

    logger.info(f"Пользователь {user.id} запустил команду /start_server")

    keyboard = await get_dynamic_keyboard(True)
    msg = await update.message.reply_text(
        "▶️ Запускаю сервер в облаке...",
        reply_markup=keyboard
    )

    # Создаем фоновую задачу
    task = asyncio.create_task(
        perform_server_operation("start", chat.id, msg.message_id, True)
    )

    active_operations[chat.id] = {
        'task': task,
        'operation_type': 'start',
        'message_id': msg.message_id
    }


async def stop_server_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик команды /stop_server (только для админов в ЛС)"""
    chat = update.effective_chat
    user = update.effective_user

    # if chat.type != "private":
    #     await update.message.reply_text("⚠️ Эта команда доступна только в личных сообщениях.")
    #     return

    if not is_admin(user.id):
        await update.message.reply_text("❌ У вас нет прав для выполнения этой команды.")
        return

    # Проверяем активные операции
    if is_operation_active(chat.id):
        await update.message.reply_text("⚠️ Уже выполняется другая операция. Дождитесь завершения.")
        return

    keyboard = await get_dynamic_keyboard(True)
    msg = await update.message.reply_text(
        "⏹️ Останавливаю сервер...",
        reply_markup=keyboard
    )

    # Создаем фоновую задачу
    task = asyncio.create_task(
        perform_server_operation("stop", chat.id, msg.message_id, True)
    )

    active_operations[chat.id] = {
        'task': task,
        'operation_type': 'stop',
        'message_id': msg.message_id
    }


async def restart_server_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик команды /restart_server (только для админов в ЛС)"""
    chat = update.effective_chat
    user = update.effective_user

    # if chat.type != "private":
    #     await update.message.reply_text("⚠️ Эта команда доступна только в личных сообщениях.")
    #     return

    if not is_admin(user.id):
        await update.message.reply_text("❌ У вас нет прав для выполнения этой команды.")
        return

    # Проверяем активные операции
    if is_operation_active(chat.id):
        await update.message.reply_text("⚠️ Уже выполняется другая операция. Дождитесь завершения.")
        return

    keyboard = await get_dynamic_keyboard(True)
    msg = await update.message.reply_text(
        "🔄 Перезагружаю сервер...",
        reply_markup=keyboard
    )

    # Создаем фоновую задачу
    task = asyncio.create_task(
        perform_server_operation("restart", chat.id, msg.message_id, True)
    )

    active_operations[chat.id] = {
        'task': task,
        'operation_type': 'restart',
        'message_id': msg.message_id
    }


async def status_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    show_admin = is_admin(user.id) and update.effective_chat.type == "private"

    keyboard = await get_dynamic_keyboard(show_admin)
    msg = await update.message.reply_text("⏳ Проверяю статус...", reply_markup=keyboard)

    result = await facade.status()
    text = ServerStatus.format_server_status(result, monitoring_enabled=idle_monitoring_enabled)

    keyboard = await get_dynamic_keyboard(show_admin)
    await msg.edit_text(
        text,
        reply_markup=keyboard,
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
    chat = update.effective_chat
    show_admin = is_admin(user.id) and (
            chat.type == "private" or chat.id == NOTIFICATION_GROUP_ID
    )

    data = query.data

    # ========== СТАТУС ==========
    if data == "status":
        await query.edit_message_text("⏳ Проверяю статус...")
        result: ServerStatus = await facade.status()
        text = ServerStatus.format_server_status(result, idle_monitoring_enabled)
        keyboard = await get_dynamic_keyboard(show_admin)
        await query.edit_message_text(
            text,
            reply_markup=keyboard,
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

        # ========== Пополнить ==========
    elif data == "popup_balance":
        result: ServerStatus = await facade.status()

        settings_text = (
            "⚙️ <b>Пополнение VPS</b>\n\n"
            f"Есть два варианта:\n"
            "<b>1.:Полуавтоматический</b>\n"
            "Вы отправляете мне на Т-банк по ссылке, дальше я оплачиваю руками через ЛК\n\n"
            "<b>2.:Автоматический</b>\n\n"
            f"Оплачивайте по ссылке введя айпи сервера <code>{result.ip}</code> (кликабельно) в поле ввода reg.cloud\n"
            "Средства будут зачислены автоматически\n\n"
            f"Текущий баланс: {result.balance}\n"
            f"Стоимость в час: {result.hour_price}\n\n"
            "Используйте кнопки ниже для выбора:"
        )
        await query.edit_message_text(
            settings_text,
            reply_markup=get_popup_balance_keyboard(),
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
        text = ServerStatus.format_server_status(result, monitoring_enabled=idle_monitoring_enabled)
        keyboard = await get_dynamic_keyboard(show_admin)
        await query.edit_message_text(
            text,
            reply_markup=keyboard,
            parse_mode="HTML",
            disable_web_page_preview=True
        )

    # ========== ОПЕРАЦИИ С СЕРВЕРОМ ==========
    elif data in ["start_server", "stop_server", "restart_server"]:
        if not show_admin:
            await query.edit_message_text("❌ У вас нет прав для выполнения этой команды.")
            return

        # Проверяем активные операции
        if is_operation_active(chat.id):
            await query.answer("⚠️ Уже выполняется другая операция", show_alert=True)
            return

        # Определяем тип операции
        operation_map = {
            "start_server": ("start", "▶️ Запускаю сервер..."),
            "stop_server": ("stop", "⏹️ Останавливаю сервер..."),
            "restart_server": ("restart", "🔄 Перезагружаю сервер...")
        }

        operation_type, initial_text = operation_map[data]

        # Обновляем сообщение
        keyboard = await get_dynamic_keyboard(True)
        await query.edit_message_text(initial_text, reply_markup=keyboard)

        # Создаем фоновую задачу
        task = asyncio.create_task(
            perform_server_operation(
                operation_type,
                chat.id,
                query.message.message_id,
                True
            )
        )

        active_operations[chat.id] = {
            'task': task,
            'operation_type': operation_type,
            'message_id': query.message.message_id
        }


async def post_init(application: Application) -> None:
    """
    Выполняется после инициализации бота
    """
    global bot_application
    bot_application = application

    logger.info("🤖 Бот инициализирован")

    # Проверяем статус сервера
    try:
        status: ServerStatus = await facade.status()
        logger.info(f"📊 Начальный статус сервера: {status.state}")

        # Запускаем мониторинг только если сервер работает
        if status.state == ServerState.READY:
            logger.info("✅ Сервер работает, запускаю мониторинг")
            start_idle_monitoring()
        else:
            logger.info(f"⏸️ Сервер в состоянии {status.state}, мониторинг не запущен")

    except Exception as e:
        logger.error(f"❌ Ошибка при проверке начального статуса: {e}")


async def post_shutdown(application: Application) -> None:
    """
    Выполняется при остановке бота
    """
    logger.info("🛑 Останавливаю бот...")
    stop_idle_monitoring()

    # Отменяем все активные операции
    for chat_id in list(active_operations.keys()):
        cancel_operation(chat_id)

    logger.info("✅ Бот остановлен")


def main():
    """Запуск бота"""
    global bot_application

    load_admin_ids()

    application = Application.builder().token(TELEGRAM_TOKEN).build()

    # ✅ Регистрируем хуки жизненного цикла
    application.post_init = post_init
    application.post_shutdown = post_shutdown

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

    logger.info("🚀 Бот запускается...")
    application.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == '__main__':
    main()