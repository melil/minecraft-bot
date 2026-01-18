#!/usr/bin/env python3
import asyncio
import logging
import os
import re
from datetime import datetime, timedelta
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CallbackQueryHandler,
    ContextTypes
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
    register_chat_handlers
)
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
            
            # Создаем inline кнопку "Ответить" с callback_data
            keyboard = InlineKeyboardMarkup([
                [InlineKeyboardButton(
                    text="💬 Ответить",
                    callback_data=f"reply_mc:{event.player_name}"
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
                reply_markup=await get_dynamic_keyboard(facade, idle_monitoring_enabled, show_admin),
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
                reply_markup=await get_dynamic_keyboard(facade, idle_monitoring_enabled, show_admin),
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
                    reply_markup=await get_dynamic_keyboard(facade, idle_monitoring_enabled, show_admin),
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
                reply_markup=await get_dynamic_keyboard(facade, idle_monitoring_enabled, show_admin),
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
                reply_markup=await get_dynamic_keyboard(facade, idle_monitoring_enabled, show_admin),
                parse_mode="HTML"
            )
        except:
            pass


# ==================== КЛАВИАТУРЫ ====================
# Клавиатуры вынесены в core/bot/keyboards.py


# ==================== КОМАНДЫ БОТА ====================
# Команды вынесены в отдельные модули core/commands/
# Здесь остаются только вспомогательные функции


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
    
    # ========== ОТВЕТ НА СООБЩЕНИЕ ИЗ MINECRAFT ==========
    if data.startswith("reply_mc:"):
        from telegram import ForceReply
        player_name = data.split(":", 1)[1]
        
        # Отправляем сообщение с force reply
        await context.bot.send_message(
            chat_id=chat.id,
            text=f"💬 Ответ для <b>{player_name}</b>:\n\nОтправьте команду в формате:\n<code>/say {player_name} ваш_текст</code>",
            parse_mode="HTML",
            reply_markup=ForceReply(
                input_field_placeholder=f"/say {player_name} ",
                selective=True
            ),
            reply_to_message_id=query.message.message_id
        )
        
        await query.answer("💬 Напишите ответ ниже")
        return
    
    # Отвечаем на callback для остальных кнопок
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
        keyboard = await get_dynamic_keyboard(facade, idle_monitoring_enabled, show_admin)
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
        keyboard = await get_dynamic_keyboard(facade, idle_monitoring_enabled, show_admin)
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
        keyboard = await get_dynamic_keyboard(facade, idle_monitoring_enabled, True)
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
        return await get_dynamic_keyboard(facade, idle_monitoring_enabled, show_admin)
    
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

    # Регистрируем обработчик кнопок
    application.add_handler(CallbackQueryHandler(button_callback))

    logger.info("🚀 Бот запускается...")
    application.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == '__main__':
    main()