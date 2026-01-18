#!/usr/bin/env python3
import asyncio
import logging
import os
import re
from datetime import datetime, timedelta
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, InlineQueryResultArticle, InputTextMessageContent
from telegram.ext import (
    Application,
    CallbackQueryHandler,
    ContextTypes,
    InlineQueryHandler
)
from core.config import TELEGRAM_TOKEN, REGRU_CLOUD_TOKEN, MINECRAFT_SERVER_ID, MINECRAFT_SERVER_SSH
from core.server.facade import ServerFacade
from core.domain.model.action_result import ActionResult
from core.domain.model.server_status import ServerStatus
from core.domain.model.server_state import ServerState
from core.api.regru import RegRuClient
from core.database import get_db, User, UserRole, Group

# Импортируем регистраторы команд
from core.bot.commands import (
    register_info_handlers,
    register_server_handlers,
    register_admin_handlers,
    register_settings_handlers,
    register_balance_handlers,
    register_chat_handlers,
    register_map_handlers
)
from core.bot.commands.stats import register_stats_handlers
from core.bot.commands.managers import OperationManager, AdminManager, SettingsManager
from core.bot.keyboards import get_dynamic_keyboard, get_settings_keyboard, get_popup_balance_keyboard

reg_ru_api = RegRuClient(REGRU_CLOUD_TOKEN, MINECRAFT_SERVER_ID)
facade = ServerFacade(reg_ru_api)

# ==================== DATABASE ====================
db = get_db()

# ==================== НАСТРОЙКИ УВЕДОМЛЕНИЙ ====================
ENABLE_ADMIN_NOTIFICATIONS = False  # ✅ Включить/выключить уведомления админам
ENABLE_GROUP_NOTIFICATIONS = True  # ✅ Включить/выключить уведомления в группу
NOTIFICATION_GROUP_ID = -5142213077  # ✅ ID группы для уведомлений (например: -1001234567890)

# ==================== BLUEMAP SETTINGS ====================
BLUEMAP_URL = "http://95.163.227.185:8100"  # URL веб-карты BlueMap

# ==================== ADMIN IDS FOR AUTO-PROMOTION ====================
# These IDs will be auto-promoted to admin on first interaction
ADMIN_IDS_FOR_AUTO_PROMOTION = [
    138349349,
    140821964,
    451548653,
    78120051,
    851242077,
    505878676,
    860938417,
]

# ==================== IDLE SHUTDOWN СИСТЕМА ====================
IDLE_SHUTDOWN_TIMEOUT = 600  # 5 минут в секундах
CHECK_INTERVAL = 30  # Проверка каждую минуту

idle_since: datetime | None = None
idle_monitoring_active = False
idle_monitoring_enabled = True  # ✅ Флаг включения/выключения автовыключения
monitoring_task = None
bot_application = None  # ✅ Глобальная ссылка на Application

# ==================== MINECRAFT LOG MONITORING ====================
# Система мониторинга событий из Minecraft (вход/выход, чат, смерти, достижения)
log_monitor = None  # Объект MonitorLogMonitor
log_monitoring_enabled = False  # ✅ Флаг включения/выключения мониторинга логов (пока выключено)

# Настройки отображения событий (можно включать/выключать отдельно)
MINECRAFT_EVENTS_CONFIG = {
    'join': True,      # Вход игроков
    'leave': True,     # Выход игроков
    'chat': True,      # Сообщения в чате
    'death': True,     # Смерти
    'achievement': True  # Достижения
}

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


def register_or_update_user(user_obj) -> User:
    """Register or update user in database"""
    if not user_obj:
        return None
    
    return db.get_or_create_user(
        telegram_id=user_obj.id,
        username=user_obj.username,
        first_name=user_obj.first_name,
        last_name=user_obj.last_name,
        auto_promote_ids=ADMIN_IDS_FOR_AUTO_PROMOTION
    )


def register_or_update_group(chat_obj) -> Group:
    """Register or update group in database"""
    if not chat_obj or chat_obj.type == "private":
        return None
    
    return db.get_or_create_group(
        telegram_id=chat_obj.id,
        title=chat_obj.title,
        username=chat_obj.username,
        chat_type=chat_obj.type
    )


def is_admin(user_id: int) -> bool:
    """Проверяет, является ли пользователь администратором"""
    return db.is_admin(user_id)


def is_super_admin(user_id: int) -> bool:
    """Проверяет, является ли пользователь супер администратором"""
    return db.is_super_admin(user_id)


# ==================== УВЕДОМЛЕНИЯ ====================

async def notify_admins(text: str):
    """Отправляет уведомления всем админам"""
    if not ENABLE_ADMIN_NOTIFICATIONS or not bot_application:
        return

    admins = db.get_all_admins()
    for admin in admins:
        try:
            await bot_application.bot.send_message(
                chat_id=admin.telegram_id,
                text=text,
                parse_mode="HTML"
            )
        except Exception as e:
            logger.error(f"Не удалось уведомить админа {admin.telegram_id}: {e}")


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


# ==================== MINECRAFT LOG MONITORING ====================

async def minecraft_event_handler(event):
    """
    Обработчик событий из Minecraft (вход/выход, чат, смерти, достижения)
    Отправляет события в группу Telegram
    """
    logger.debug(f"🎯 Получено событие: {event.event_type}")
    
    if not bot_application:
        logger.warning("⚠️ bot_application не инициализирован!")
        return
    
    # Сообщения с префиксом "tg:" отправляются ВСЕГДА, независимо от настроек
    if event.event_type == 'telegram_message':
        logger.info(f"📨 Обработка tg-сообщения от {event.player_name}")
        try:
            from telegram import InlineKeyboardButton, InlineKeyboardMarkup
            
            # Используем встроенный метод форматирования
            message = event.format_telegram()
            
            # Создаем inline кнопку "Ответить" с inline query
            keyboard = InlineKeyboardMarkup([
                [InlineKeyboardButton(
                    text="💬 Ответить",
                    switch_inline_query_current_chat=f"/say {event.player_name} "
                )]
            ])
            
            logger.info(f"📤 Отправка в группу {NOTIFICATION_GROUP_ID}: {message}")
            await bot_application.bot.send_message(
                chat_id=NOTIFICATION_GROUP_ID,
                text=message,
                parse_mode="HTML",
                reply_markup=keyboard
            )
            logger.info(f"✅ Сообщение из Minecraft отправлено в Telegram: {event.player_name}")
        except Exception as e:
            logger.error(f"❌ Ошибка отправки tg-сообщения: {e}", exc_info=True)
        return
    
    # Для остальных событий проверяем, включен ли мониторинг
    if not log_monitoring_enabled:
        logger.debug(f"⏭️ Мониторинг выключен, событие {event.event_type} пропущено")
        return
    
    # Проверяем, включен ли данный тип события
    if not MINECRAFT_EVENTS_CONFIG.get(event.event_type, False):
        logger.debug(f"⏭️ Тип события {event.event_type} отключен в конфиге")
        return
    
    logger.info(f"📬 Отправка события {event.event_type} в Telegram")
    try:
        from core.minecraft.log_monitor import send_event_to_telegram
        
        await send_event_to_telegram(
            event,
            bot_application,
            NOTIFICATION_GROUP_ID,
            MINECRAFT_EVENTS_CONFIG
        )
    except Exception as e:
        logger.error(f"❌ Ошибка обработки события Minecraft: {e}", exc_info=True)


async def start_log_monitoring():
    """Запускает мониторинг логов Minecraft"""
    global log_monitor
    
    logger.info("🚀 Запуск мониторинга логов Minecraft...")
    
    if log_monitor and log_monitor.is_running:
        logger.warning("⚠️ Мониторинг логов уже запущен")
        return
    
    try:
        from core.minecraft.log_monitor import MinecraftLogMonitor
        
        logger.info(f"📝 Создание MinecraftLogMonitor с интервалом 2с")
        log_monitor = MinecraftLogMonitor(
            ssh_config=MINECRAFT_SERVER_SSH,
            event_callback=minecraft_event_handler,
            check_interval=2  # Проверка каждые 2 секунды
        )
        
        logger.info("▶️ Вызов log_monitor.start()...")
        await log_monitor.start()
        logger.info(f"✅ Мониторинг логов Minecraft запущен (is_running={log_monitor.is_running})")
        
    except Exception as e:
        logger.error(f"❌ Ошибка запуска мониторинга логов: {e}", exc_info=True)


async def stop_log_monitoring():
    """Останавливает мониторинг логов Minecraft"""
    global log_monitor
    
    if log_monitor:
        await log_monitor.stop()
        log_monitor = None
        logger.info("🛑 Мониторинг логов Minecraft остановлен")


def toggle_log_monitoring() -> bool:
    """Переключает режим мониторинга логов"""
    global log_monitoring_enabled
    
    log_monitoring_enabled = not log_monitoring_enabled
    logger.info(f"🔄 Мониторинг логов {'включен' if log_monitoring_enabled else 'отключен'}")
    return log_monitoring_enabled


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
                reply_markup=await get_dynamic_keyboard(facade, idle_monitoring_enabled, show_admin, BLUEMAP_URL),
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
                reply_markup=await get_dynamic_keyboard(facade, idle_monitoring_enabled, show_admin, BLUEMAP_URL),
                parse_mode="HTML",
                disable_web_page_preview=True
            )

            # Проверяем достижение целевого состояния
            if status.state == target_state:
                logger.info(f"Операция {operation_type} завершена успешно")

                # Управление мониторингом
                if operation_type == "start" or operation_type == "restart":
                    start_idle_monitoring()
                    # Запускаем мониторинг логов ВСЕГДА (для tg-сообщений)
                    await start_log_monitoring()
                elif operation_type == "stop":
                    stop_idle_monitoring()
                    # Останавливаем мониторинг логов
                    await stop_log_monitoring()

                # Финальное сообщение
                await bot_application.bot.edit_message_text(
                    chat_id=chat_id,
                    message_id=message_id,
                    text=f"{success_message}\n\n{ServerStatus.format_server_status(status, monitoring_enabled=idle_monitoring_enabled)}",
                    reply_markup=await get_dynamic_keyboard(facade, idle_monitoring_enabled, show_admin, BLUEMAP_URL),
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
                reply_markup=await get_dynamic_keyboard(facade, idle_monitoring_enabled, show_admin, BLUEMAP_URL),
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
                reply_markup=await get_dynamic_keyboard(facade, idle_monitoring_enabled, show_admin, BLUEMAP_URL),
                parse_mode="HTML"
            )
        except:
            pass


# ==================== КЛАВИАТУРЫ ====================
# Клавиатуры вынесены в core/bot/keyboards.py


# ==================== КОМАНДЫ БОТА ====================
# Команды вынесены в отдельные модули core/commands/
# Здесь остаются только вспомогательные функции


# ==================== ОБРАБОТЧИК INLINE ЗАПРОСОВ ====================

async def inline_query_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик inline запросов для быстрых ответов в Minecraft"""
    query = update.inline_query.query
    
    logger.info(f"📥 Inline query получен: '{query}'")
    
    # Проверяем, что запрос начинается с /say
    if not query.startswith('/say '):
        logger.debug(f"⏭️ Inline query не начинается с /say, пропуск")
        await update.inline_query.answer([])
        return
    
    # Парсим команду: /say PlayerName text
    parts = query.split(' ', 2)
    if len(parts) < 2:
        logger.debug(f"⏭️ Inline query слишком короткий, нужен ник игрока")
        await update.inline_query.answer([])
        return
    
    player_name = parts[1] if len(parts) > 1 else ""
    message_text = parts[2] if len(parts) > 2 else ""
    
    logger.info(f"✅ Создаю inline результат для /say {player_name}")
    
    # Создаем результат
    results = [
        InlineQueryResultArticle(
            id='say_command',
            title=f'📤 Отправить в Minecraft',
            description=f'{query}',
            input_message_content=InputTextMessageContent(
                message_text=query
            )
        )
    ]
    
    await update.inline_query.answer(results, cache_time=0)
    logger.info(f"📤 Inline результат отправлен")


# ==================== ОБРАБОТЧИК КНОПОК ====================

async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик нажатий на inline кнопки"""
    query = update.callback_query
    
    user = update.effective_user
    chat = update.effective_chat
    
    # Register or update user in database
    register_or_update_user(user)
    
    # Register group if in group
    if chat.type in ["group", "supergroup"]:
        register_or_update_group(chat)
    
    data = query.data
    
    # Отвечаем на callback
    await query.answer()
    
    # Логика прав доступа:
    # - В группе: все участники группы могут нажимать кнопки
    # - В личке: только админы могут нажимать кнопки управления
    is_group_chat = chat.id == NOTIFICATION_GROUP_ID
    is_private_chat = chat.type == "private"
    is_user_admin = is_admin(user.id)
    
    # Показываем админские кнопки если:
    # 1. Это группа (все участники группы видят кнопки управления)
    # 2. Это личка с ботом И пользователь админ
    show_admin = is_group_chat or (is_private_chat and is_user_admin)

    # ========== СТАТУС ==========
    if data == "status":
        await query.edit_message_text("⏳ Проверяю статус...")
        result: ServerStatus = await facade.status()
        text = ServerStatus.format_server_status(result, idle_monitoring_enabled)
        keyboard = await get_dynamic_keyboard(facade, idle_monitoring_enabled, show_admin, BLUEMAP_URL)
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
        log_status = "🟢 Включен" if log_monitoring_enabled else "🔴 Отключен"
        settings_text = (
            "⚙️ <b>Настройки сервера</b>\n\n"
            f"⏱️ <b>Автовыключение:</b> {auto_status}\n"
            f"<i>Сервер выключается через {IDLE_SHUTDOWN_TIMEOUT // 60} мин. при 0 игроков</i>\n\n"
            f"📜 <b>Мониторинг событий MC:</b> {log_status}\n"
            f"<i>События из Minecraft (вход/выход, чат, смерти, достижения)</i>\n"
            f"<i>💡 Сообщения с префиксом 'tg:' всегда передаются в Telegram</i>\n\n"
            "Используйте кнопки ниже для изменения настроек:"
        )
        await query.edit_message_text(
            settings_text,
            reply_markup=get_settings_keyboard(idle_monitoring_enabled, log_monitoring_enabled),
            parse_mode="HTML"
        )

        # ========== Пополнить ==========
    elif data == "popup_balance":
        result: ServerStatus = await facade.status()

        settings_text = (
            "⚙️ <b>Пополнение VPS</b>\n\n"
            f"Есть два варианта:\n"
            "<b>🟨.:Полуавтоматический</b>\n"
            "Банковская карта (номер, срок действия, cvv)\n"
            "Вы оплачиваете деньги на счет в Т-банк по ссылке, дальше я оплачиваю руками через ЛК\n\n"
            "<b>🟩.:Автоматический</b>\n"
            "СБП, Банковская карта, Ю-мани, Кэш, СберПей\n"
            f"Оплачивайте по ссылке введя айпи сервера <code>{result.ip}</code> (кликабельно) в поле ввода reg.cloud/prolong\n"
            "Средства будут зачислены автоматически\n\n"
            "Минимальная сумма пополнения: 100 ₽\n\n"
            f"Текущий баланс: {result.balance} ₽\n"
        )

        if result.state == ServerState.READY:
            settings_text += f"Стоимость в час: {result.hour_price} ₽\n\n"

        settings_text +=  "Используйте кнопки ниже для выбора:"

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
        log_status = "🟢 Включен" if log_monitoring_enabled else "🔴 Отключен"
        settings_text = (
            "⚙️ <b>Настройки сервера</b>\n\n"
            f"⏱️ <b>Автовыключение:</b> {auto_status}\n"
            f"<i>Сервер выключается через {IDLE_SHUTDOWN_TIMEOUT // 60} мин. при 0 игроков</i>\n\n"
            f"📜 <b>Мониторинг событий MC:</b> {log_status}\n"
            f"<i>События из Minecraft (вход/выход, чат, смерти, достижения)</i>\n"
            f"<i>💡 Сообщения с префиксом 'tg:' всегда передаются в Telegram</i>\n\n"
            "Используйте кнопки ниже для изменения настроек:"
        )
        await query.edit_message_text(
            settings_text,
            reply_markup=get_settings_keyboard(new_state, log_monitoring_enabled),
            parse_mode="HTML"
        )
    
    # ========== ПЕРЕКЛЮЧЕНИЕ МОНИТОРИНГА ЛОГОВ ==========
    elif data == "toggle_log_monitoring":
        if not show_admin:
            await query.answer("❌ У вас нет прав", show_alert=True)
            return
        
        new_state = toggle_log_monitoring()
        status_emoji = "🟢" if new_state else "🔴"
        status_text = "включен" if new_state else "отключен"
        
        await query.answer(f"{status_emoji} Мониторинг событий {status_text}", show_alert=True)
        
        # Мониторинг логов работает всегда (для tg-сообщений), 
        # но флаг log_monitoring_enabled контролирует отправку обычных событий
        logger.info(f"🔄 Мониторинг событий переключен: {new_state} (tg-сообщения всегда работают)")
        
        # Обновляем меню настроек
        auto_status = "🟢 Включено" if idle_monitoring_enabled else "🔴 Отключено"
        log_status = "🟢 Включен" if new_state else "🔴 Отключен"
        settings_text = (
            "⚙️ <b>Настройки сервера</b>\n\n"
            f"⏱️ <b>Автовыключение:</b> {auto_status}\n"
            f"<i>Сервер выключается через {IDLE_SHUTDOWN_TIMEOUT // 60} мин. при 0 игроков</i>\n\n"
            f"📜 <b>Мониторинг событий MC:</b> {log_status}\n"
            f"<i>События из Minecraft (вход/выход, чат, смерти, достижения)</i>\n"
            f"<i>💡 Сообщения с префиксом 'tg:' всегда передаются в Telegram</i>\n\n"
            "Используйте кнопки ниже для изменения настроек:"
        )
        await query.edit_message_text(
            settings_text,
            reply_markup=get_settings_keyboard(idle_monitoring_enabled, new_state),
            parse_mode="HTML"
        )

    # ========== НАЗАД ==========
    elif data == "back_to_main":
        result: ServerStatus = await facade.status()
        text = ServerStatus.format_server_status(result, monitoring_enabled=idle_monitoring_enabled)
        keyboard = await get_dynamic_keyboard(facade, idle_monitoring_enabled, show_admin, BLUEMAP_URL)
        await query.edit_message_text(
            text,
            reply_markup=keyboard,
            parse_mode="HTML",
            disable_web_page_preview=True
        )

    # ========== МЕНЮ СТАТИСТИКИ ==========
    elif data == "stats_menu":
        from core.bot.keyboards import get_stats_menu_keyboard
        
        message_text = (
            "📈 <b>Статистика игроков</b>\n\n"
            "Выберите действие:"
        )
        
        await query.edit_message_text(
            message_text,
            reply_markup=get_stats_menu_keyboard(),
            parse_mode="HTML"
        )

    # ========== ВЫБОР ИГРОКА ==========
    elif data == "stats_select_player":
        from core.minecraft.stats import get_all_players_list, get_usercache
        from core.bot.keyboards import get_players_list_keyboard
        
        await query.answer("⏳ Загружаю список игроков...")
        
        try:
            # Загружаем список игроков
            uuids = await get_all_players_list(MINECRAFT_SERVER_SSH)
            usercache = await get_usercache(MINECRAFT_SERVER_SSH)
            
            if not uuids:
                await query.edit_message_text(
                    "❌ На сервере еще не было игроков",
                    reply_markup=get_stats_menu_keyboard(),
                    parse_mode="HTML"
                )
                return
            
            # Создаем список игроков с никнеймами
            from core.minecraft.stats import uuid_to_username
            players = []
            for uuid in uuids:
                nickname = await uuid_to_username(MINECRAFT_SERVER_SSH, uuid, usercache)
                players.append({'nickname': nickname, 'uuid': uuid})
            
            # Сортируем по никнейму
            players.sort(key=lambda p: p['nickname'].lower())
            
            # Сохраняем список в контексте для пагинации
            context.bot_data[f'players_list_{chat.id}'] = players
            
            await query.edit_message_text(
                f"👥 <b>Выберите игрока ({len(players)})</b>",
                reply_markup=get_players_list_keyboard(players, page=0),
                parse_mode="HTML"
            )
            
        except Exception as e:
            logger.error(f"❌ Ошибка загрузки списка игроков: {e}", exc_info=True)
            await query.edit_message_text(
                f"❌ Ошибка: {str(e)}",
                reply_markup=get_stats_menu_keyboard(),
                parse_mode="HTML"
            )

    # ========== ПАГИНАЦИЯ СПИСКА ИГРОКОВ ==========
    elif data.startswith("stats_page:"):
        from core.bot.keyboards import get_players_list_keyboard
        
        page = int(data.split(":")[1])
        players = context.bot_data.get(f'players_list_{chat.id}', [])
        
        if not players:
            await query.answer("❌ Список игроков устарел, загрузите заново", show_alert=True)
            return
        
        await query.edit_message_text(
            f"👥 <b>Выберите игрока ({len(players)})</b>",
            reply_markup=get_players_list_keyboard(players, page=page),
            parse_mode="HTML"
        )

    # ========== ПРОСМОТР СТАТИСТИКИ ИГРОКА ==========
    elif data.startswith("stats_player:"):
        from core.minecraft.stats import get_player_stats, find_player_by_nickname
        from core.bot.keyboards import get_stats_menu_keyboard
        
        await query.answer("⏳ Загружаю статистику...")
        
        try:
            uuid_short = data.split(":")[1]
            
            # Находим полный UUID из сохраненного списка
            players = context.bot_data.get(f'players_list_{chat.id}', [])
            player_uuid = None
            player_nickname = None
            
            for p in players:
                if p['uuid'].startswith(uuid_short):
                    player_uuid = p['uuid']
                    player_nickname = p['nickname']
                    break
            
            if not player_uuid:
                await query.answer("❌ Игрок не найден", show_alert=True)
                return
            
            # Проверяем кэш (только если содержит новые поля)
            cached = db.get_cached_player_stats(player_uuid, cache_minutes=5)
            use_cache = cached and hasattr(cached, 'blocks_mined') and cached.blocks_mined is not None
            
            if use_cache:
                stats = {
                    'nickname': cached.minecraft_nickname,
                    'playtime_ticks': cached.playtime_ticks,
                    'deaths': cached.deaths,
                    'mob_kills': cached.mob_kills,
                    'jumps': cached.jumps,
                    'blocks_mined': cached.blocks_mined,
                    'damage_dealt': cached.damage_dealt,
                    'damage_taken': cached.damage_taken,
                }
                from core.minecraft.stats import format_playtime, ticks_to_timedelta
                stats['playtime_formatted'] = format_playtime(ticks_to_timedelta(cached.playtime_ticks))
            else:
                # Загружаем с сервера
                stats = await get_player_stats(MINECRAFT_SERVER_SSH, player_uuid, player_nickname)
                
                if not stats:
                    await query.edit_message_text(
                        f"❌ Не удалось загрузить статистику",
                        reply_markup=get_stats_menu_keyboard(),
                        parse_mode="HTML"
                    )
                    return
                
                # Сохраняем в кэш
                from datetime import datetime
                db.update_player_stats(
                    minecraft_uuid=player_uuid,
                    minecraft_nickname=stats['nickname'],
                    playtime_ticks=stats['playtime_ticks'],
                    deaths=stats.get('deaths', 0),
                    mob_kills=stats.get('mob_kills', 0),
                    jumps=stats.get('jumps', 0),
                    blocks_mined=stats.get('blocks_mined', 0),
                    damage_dealt=stats.get('damage_dealt', 0),
                    damage_taken=stats.get('damage_taken', 0),
                    last_seen=datetime.utcnow()
                )
            
            # Формируем сообщение
            message = (
                f"📊 <b>Статистика игрока {stats['nickname']}</b>\n\n"
                f"⏱️ <b>Время в игре:</b> {stats['playtime_formatted']}\n"
                f"💀 <b>Смертей:</b> {stats.get('deaths', 0)}\n"
                f"⚔️ <b>Убито мобов:</b> {stats.get('mob_kills', 0)}\n"
                f"⛏️ <b>Добыто блоков:</b> {stats.get('blocks_mined', 0)}\n"
                f"🦘 <b>Прыжков:</b> {stats.get('jumps', 0)}\n"
            )
            
            # Используем клавиатуру с детальной статистикой
            from core.bot.keyboards import get_player_stats_keyboard
            uuid_short = player_uuid[:8]
            
            # Сохраняем полный UUID в контексте для детальной статистики
            context.bot_data[f'player_uuid_{uuid_short}'] = player_uuid
            context.bot_data[f'player_stats_{uuid_short}'] = stats
            
            await query.edit_message_text(
                message,
                reply_markup=get_player_stats_keyboard(uuid_short),
                parse_mode="HTML"
            )
            
        except Exception as e:
            logger.error(f"❌ Ошибка загрузки статистики: {e}", exc_info=True)
            await query.edit_message_text(
                f"❌ Ошибка: {str(e)}",
                reply_markup=get_stats_menu_keyboard(),
                parse_mode="HTML"
            )

    # ========== ТОП ИГРОКОВ ==========
    elif data == "stats_top":
        from core.minecraft.stats import get_top_players_by_playtime, format_playtime, ticks_to_timedelta
        from core.bot.keyboards import get_stats_menu_keyboard
        
        await query.answer("⏳ Загружаю топ игроков...")
        
        try:
            # ВСЕГДА загружаем свежие данные с сервера для точного топа
            logger.info("🔄 Загрузка свежего топа с сервера")
            top_players = await get_top_players_by_playtime(MINECRAFT_SERVER_SSH, limit=10, force_reload=True)
            
            if not top_players:
                await query.edit_message_text(
                    "❌ Не удалось загрузить топ игроков",
                    reply_markup=get_stats_menu_keyboard(),
                    parse_mode="HTML"
                )
                return
            
            # Обновляем кэш
            for player in top_players:
                db.update_player_stats(
                    minecraft_uuid=player['uuid'],
                    minecraft_nickname=player['nickname'],
                    playtime_ticks=player['playtime_ticks'],
                    deaths=player.get('deaths', 0),
                    mob_kills=player.get('mob_kills', 0),
                    jumps=player.get('jumps', 0),
                    blocks_mined=player.get('blocks_mined', 0),
                    damage_dealt=player.get('damage_dealt', 0),
                    damage_taken=player.get('damage_taken', 0)
                )
            
            # Формируем сообщение
            if not top_players:
                await query.edit_message_text(
                    "❌ На сервере еще не было игроков",
                    reply_markup=get_stats_menu_keyboard(),
                    parse_mode="HTML"
                )
                return
            
            message_lines = [f"🏆 <b>Топ {len(top_players)} игроков по времени игры</b>\n"]
            
            medals = ["🥇", "🥈", "🥉"]
            for i, player in enumerate(top_players, 1):
                medal = medals[i-1] if i <= 3 else f"{i}."
                nickname = player['nickname']
                playtime = player['playtime_formatted']
                
                message_lines.append(f"{medal} <b>{nickname}</b> — {playtime}")
            
            message = "\n".join(message_lines)
            await query.edit_message_text(
                message,
                reply_markup=get_stats_menu_keyboard(),
                parse_mode="HTML"
            )
            
        except Exception as e:
            logger.error(f"❌ Ошибка загрузки топа: {e}", exc_info=True)
            await query.edit_message_text(
                f"❌ Ошибка: {str(e)}",
                reply_markup=get_stats_menu_keyboard(),
                parse_mode="HTML"
            )

    # ========== ДЕТАЛЬНАЯ СТАТИСТИКА ==========
    elif data.startswith("stats_detail:"):
        from core.minecraft.stats import get_top_killed_mobs, get_top_mined_blocks, get_top_deaths_from
        from core.bot.keyboards import get_player_stats_keyboard
        
        try:
            parts = data.split(":")
            uuid_short = parts[1]
            detail_type = parts[2]
            
            # Получаем сохраненную статистику
            stats = context.bot_data.get(f'player_stats_{uuid_short}')
            
            if not stats:
                await query.answer("❌ Данные устарели, загрузите статистику заново", show_alert=True)
                await query.edit_message_text(
                    "❌ Данные устарели",
                    reply_markup=get_stats_menu_keyboard(),
                    parse_mode="HTML"
                )
                return
            
            nickname = stats['nickname']
            
            # Формируем сообщение в зависимости от типа
            if detail_type == "mobs":
                top_mobs = get_top_killed_mobs(stats.get('killed_detailed', {}), limit=10)
                
                message = f"⚔️ <b>Убито мобов — {nickname}</b>\n\n"
                message += f"<b>Всего убито:</b> {stats.get('mob_kills', 0)}\n\n"
                
                if top_mobs:
                    message += "<b>Топ-10:</b>\n"
                    for i, (mob_name, count) in enumerate(top_mobs, 1):
                        message += f"{i}. <b>{mob_name}:</b> {count}\n"
                else:
                    message += "<i>Данных нет</i>"
            
            elif detail_type == "blocks":
                top_blocks = get_top_mined_blocks(stats.get('mined_detailed', {}), limit=10)
                
                message = f"⛏️ <b>Добыто блоков — {nickname}</b>\n\n"
                message += f"<b>Всего добыто:</b> {stats.get('blocks_mined', 0)}\n\n"
                
                if top_blocks:
                    message += "<b>Топ-10:</b>\n"
                    for i, (block_name, count) in enumerate(top_blocks, 1):
                        message += f"{i}. <b>{block_name}:</b> {count}\n"
                else:
                    message += "<i>Данных нет</i>"
            
            elif detail_type == "deaths":
                top_deaths = get_top_deaths_from(stats.get('killed_by_detailed', {}), limit=10)
                
                message = f"💀 <b>Смерти — {nickname}</b>\n\n"
                message += f"<b>Всего смертей:</b> {stats.get('deaths', 0)}\n\n"
                
                if top_deaths:
                    message += "<b>Топ причин:</b>\n"
                    for i, (cause, count) in enumerate(top_deaths, 1):
                        message += f"{i}. <b>{cause}:</b> {count}\n"
                else:
                    message += "<i>Данных нет</i>"
            
            elif detail_type == "damage":
                damage_dealt = stats.get('damage_dealt', 0)
                damage_taken = stats.get('damage_taken', 0)
                
                # Конвертируем в обычные единицы (делим на 10, так как хранится в десятых долях)
                damage_dealt_hp = damage_dealt / 10
                damage_taken_hp = damage_taken / 10
                
                message = f"💥 <b>Урон — {nickname}</b>\n\n"
                message += f"⚔️ <b>Нанесено урона:</b> {damage_dealt_hp:.1f} ❤️\n"
                message += f"💔 <b>Получено урона:</b> {damage_taken_hp:.1f} ❤️\n\n"
                
                if damage_dealt > 0 and damage_taken > 0:
                    ratio = damage_dealt / damage_taken
                    message += f"📊 <b>Соотношение:</b> {ratio:.2f}\n"
                    
                    if ratio > 2:
                        message += "<i>⭐ Отличный боец!</i>"
                    elif ratio > 1:
                        message += "<i>✓ Хороший результат</i>"
                    elif ratio > 0.5:
                        message += "<i>≈ Средний уровень</i>"
                    else:
                        message += "<i>⚠ Нужно быть осторожнее</i>"
            
            await query.edit_message_text(
                message,
                reply_markup=get_player_stats_keyboard(uuid_short),
                parse_mode="HTML"
            )
            
        except Exception as e:
            logger.error(f"❌ Ошибка детальной статистики: {e}", exc_info=True)
            await query.answer(f"❌ Ошибка: {str(e)}", show_alert=True)

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
        keyboard = await get_dynamic_keyboard(facade, idle_monitoring_enabled, True, BLUEMAP_URL)
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
            
            # Запускаем мониторинг логов ВСЕГДА (для отслеживания "tg" сообщений)
            await start_log_monitoring()
            logger.info(f"📜 Мониторинг логов запущен (tg-сообщения: всегда, остальные: {log_monitoring_enabled})")
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
    
    # Останавливаем мониторинг логов
    await stop_log_monitoring()

    # Отменяем все активные операции
    for chat_id in list(active_operations.keys()):
        cancel_operation(chat_id)

    logger.info("✅ Бот остановлен")


def main():
    """Запуск бота"""
    global bot_application

    application = Application.builder().token(TELEGRAM_TOKEN).build()

    # ✅ Регистрируем хуки жизненного цикла
    application.post_init = post_init
    application.post_shutdown = post_shutdown

    # ✅ Создаем менеджеры
    operation_manager = OperationManager(active_operations, perform_server_operation)
    
    # Create database-based admin manager
    class DatabaseAdminManager:
        """Database-based admin manager"""
        def add_admin(self, telegram_id: int):
            # First, ensure user exists
            user = db.get_user_by_telegram_id(telegram_id)
            if not user:
                # Create user if doesn't exist
                user = db.get_or_create_user(telegram_id, auto_promote_ids=[])
            db.update_user_role(telegram_id, UserRole.ADMIN)
        
        def remove_admin(self, telegram_id: int) -> bool:
            user = db.get_user_by_telegram_id(telegram_id)
            if user and user.role in [UserRole.ADMIN, UserRole.SUPER_ADMIN]:
                if user.role == UserRole.SUPER_ADMIN:
                    return False  # Cannot remove super admin
                db.update_user_role(telegram_id, UserRole.USER)
                return True
            return False
        
        def get_admins(self):
            admins = db.get_all_admins()
            result = []
            for user in admins:
                role_emoji = "👑" if user.is_super_admin() else "🔑"
                display = f"{user.telegram_id} {role_emoji}"
                if user.username:
                    display += f" @{user.username}"
                if user.minecraft_nickname:
                    display += f" (MC: {user.minecraft_nickname})"
                result.append(display)
            return result
        
        def set_minecraft_nickname(self, telegram_id: int, nickname: str) -> bool:
            return db.update_user_minecraft_nickname(telegram_id, nickname)
        
        def is_super_admin(self, telegram_id: int) -> bool:
            return db.is_super_admin(telegram_id)
        
        def promote_super_admin(self, telegram_id: int) -> bool:
            user = db.get_user_by_telegram_id(telegram_id)
            if not user:
                # Create user if doesn't exist
                user = db.get_or_create_user(telegram_id, auto_promote_ids=[])
            return db.update_user_role(telegram_id, UserRole.SUPER_ADMIN)
    
    admin_manager = DatabaseAdminManager()
    
    settings_manager = SettingsManager(
        toggle_auto_shutdown,
        lambda: idle_monitoring_enabled,
        lambda: get_settings_keyboard(idle_monitoring_enabled, log_monitoring_enabled)
    )
    
    # Обертки для клавиатур
    async def keyboard_builder(show_admin: bool):
        return await get_dynamic_keyboard(facade, idle_monitoring_enabled, show_admin, BLUEMAP_URL)
    
    def balance_keyboard_builder():
        return get_popup_balance_keyboard()
    
    # Wrapper for is_admin that also registers users
    def is_admin_with_registration(user_id: int, user_obj=None) -> bool:
        if user_obj:
            register_or_update_user(user_obj)
        return is_admin(user_id)

    # ✅ Регистрируем команды через модули
    register_info_handlers(
        application,
        facade,
        is_admin,
        keyboard_builder,
        lambda: idle_monitoring_enabled,
        register_or_update_user,
        register_or_update_group
    )
    
    register_server_handlers(
        application,
        facade,
        is_admin,
        keyboard_builder,
        operation_manager,
        register_or_update_user,
        register_or_update_group
    )
    
    register_admin_handlers(
        application,
        facade,
        is_admin,
        keyboard_builder,
        admin_manager,
        register_or_update_user,
        register_or_update_group
    )
    
    register_settings_handlers(
        application,
        facade,
        is_admin,
        keyboard_builder,
        settings_manager,
        IDLE_SHUTDOWN_TIMEOUT,
        register_or_update_user,
        register_or_update_group
    )
    
    register_balance_handlers(
        application,
        facade,
        is_admin,
        keyboard_builder,
        balance_keyboard_builder,
        register_or_update_user,
        register_or_update_group
    )
    
    register_chat_handlers(
        application,
        facade,
        is_admin,
        is_super_admin,
        keyboard_builder,
        MINECRAFT_SERVER_SSH,
        lambda: idle_monitoring_enabled,
        register_or_update_user,
        register_or_update_group
    )
    
    # Регистрируем обработчики команд карты
    from core.bluemap import BlueMapAPI
    bluemap_api = BlueMapAPI(BLUEMAP_URL, MINECRAFT_SERVER_SSH)
    
    register_map_handlers(
        application,
        bluemap_api,
        register_or_update_user,
        register_or_update_group
    )
    
    # Регистрируем обработчики команд статистики
    register_stats_handlers(
        application,
        facade,
        is_admin,
        keyboard_builder,
        register_or_update_user,
        register_or_update_group
    )

    # Регистрируем обработчик inline запросов
    application.add_handler(InlineQueryHandler(inline_query_handler))
    
    # Регистрируем обработчик кнопок
    application.add_handler(CallbackQueryHandler(button_callback))

    logger.info("🚀 Бот запускается...")
    application.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == '__main__':
    main()