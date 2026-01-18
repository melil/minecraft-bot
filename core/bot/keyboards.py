"""
Клавиатуры для Telegram бота
"""
import logging
from telegram import InlineKeyboardButton, InlineKeyboardMarkup

from core.domain.model.server_status import ServerStatus
from core.domain.model.server_state import ServerState

logger = logging.getLogger(__name__)


async def get_dynamic_keyboard(
    facade,
    idle_monitoring_enabled: bool,
    show_admin_buttons: bool = False
) -> InlineKeyboardMarkup:
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


def get_settings_keyboard(idle_monitoring_enabled: bool, log_monitoring_enabled: bool = False) -> InlineKeyboardMarkup:
    """Клавиатура настроек"""
    auto_status = "🟢 ВКЛ" if idle_monitoring_enabled else "🔴 ВЫКЛ"
    log_status = "🟢 ВКЛ" if log_monitoring_enabled else "🔴 ВЫКЛ"

    keyboard = [
        [InlineKeyboardButton(
            f"⏱️ Автовыключение: {auto_status}",
            callback_data="toggle_auto_shutdown"
        )],
        [InlineKeyboardButton(
            f"📜 Мониторинг событий MC: {log_status}",
            callback_data="toggle_log_monitoring"
        )],
        [InlineKeyboardButton("◀️ Назад", callback_data="back_to_main")]
    ]

    return InlineKeyboardMarkup(keyboard)


def get_popup_balance_keyboard() -> InlineKeyboardMarkup:
    """Клавиатура пополнения баланса"""
    keyboard = [
        [InlineKeyboardButton(
            f"🟨",
            url="https://www.tbank.ru/cf/2dzkoyJFsJc"
        ), InlineKeyboardButton(
            f"🟩",
            url="https://reg.cloud/prolong"
        )],
        [InlineKeyboardButton("◀️ Назад", callback_data="back_to_main")]
    ]

    return InlineKeyboardMarkup(keyboard)
