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
    show_admin_buttons: bool = False,
    bluemap_url: str = None
) -> InlineKeyboardMarkup:
    """Создает динамическую клавиатуру в зависимости от состояния сервера"""
    keyboard = [
        [
            InlineKeyboardButton("📊 Статус", callback_data="status"),
            InlineKeyboardButton("💵 Пополнить", callback_data="popup_balance")
        ],
        [
            InlineKeyboardButton("📈 Статистика", callback_data="stats_menu")
        ]
    ]
    
    # Добавляем кнопку карты если URL предоставлен
    if bluemap_url:
        keyboard.append([
            InlineKeyboardButton("🗺️ Карта сервера", url=bluemap_url)
        ])

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


def get_stats_menu_keyboard() -> InlineKeyboardMarkup:
    """Клавиатура меню статистики"""
    keyboard = [
        [InlineKeyboardButton("👥 Выбрать игрока", callback_data="stats_select_player")],
        [InlineKeyboardButton("🏆 Топ игроков", callback_data="stats_top")],
        [InlineKeyboardButton("◀️ Назад", callback_data="back_to_main")]
    ]
    
    return InlineKeyboardMarkup(keyboard)


def get_player_stats_keyboard(player_uuid_short: str) -> InlineKeyboardMarkup:
    """
    Клавиатура для просмотра детальной статистики игрока
    
    Args:
        player_uuid_short: первые 8 символов UUID
    """
    keyboard = [
        [
            InlineKeyboardButton("⚔️ Мобы", callback_data=f"stats_detail:{player_uuid_short}:mobs"),
            InlineKeyboardButton("⛏️ Блоки", callback_data=f"stats_detail:{player_uuid_short}:blocks")
        ],
        [
            InlineKeyboardButton("💀 Смерти", callback_data=f"stats_detail:{player_uuid_short}:deaths"),
            InlineKeyboardButton("💥 Урон", callback_data=f"stats_detail:{player_uuid_short}:damage")
        ],
        [InlineKeyboardButton("◀️ Назад к меню", callback_data="stats_menu")]
    ]
    
    return InlineKeyboardMarkup(keyboard)


def get_players_list_keyboard(players: list, page: int = 0, page_size: int = 10) -> InlineKeyboardMarkup:
    """
    Клавиатура со списком игроков для выбора
    
    Args:
        players: список словарей с данными игроков [{nickname: str, uuid: str}, ...]
        page: номер страницы (0-based)
        page_size: количество игроков на странице
    """
    start_idx = page * page_size
    end_idx = start_idx + page_size
    page_players = players[start_idx:end_idx]
    
    keyboard = []
    
    # Создаем кнопки по 2 в ряд
    for i in range(0, len(page_players), 2):
        row = []
        for j in range(2):
            idx = i + j
            if idx < len(page_players):
                player = page_players[idx]
                row.append(InlineKeyboardButton(
                    player['nickname'],
                    callback_data=f"stats_player:{player['uuid'][:8]}"
                ))
        keyboard.append(row)
    
    # Навигация по страницам
    nav_buttons = []
    total_pages = (len(players) + page_size - 1) // page_size
    
    if page > 0:
        nav_buttons.append(InlineKeyboardButton("◀️ Пред.", callback_data=f"stats_page:{page-1}"))
    
    if page < total_pages - 1:
        nav_buttons.append(InlineKeyboardButton("След. ▶️", callback_data=f"stats_page:{page+1}"))
    
    if nav_buttons:
        keyboard.append(nav_buttons)
    
    # Кнопка назад
    keyboard.append([InlineKeyboardButton("◀️ Назад к меню", callback_data="stats_menu")])
    
    return InlineKeyboardMarkup(keyboard)
