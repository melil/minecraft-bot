# core/domain/model/server_status.py
from dataclasses import dataclass
from typing import Optional, TYPE_CHECKING, List
from html import escape

from core.domain.model.server_state import ServerState

if TYPE_CHECKING:
    pass

PLAYER_ID_MAP = {
    "Trudovick": 78120051,
    "PAPIN_TYZ": 505878676,
    "orlan1211": 860938417,
    "_zari_1": 451548653,
    "_SoftEclipse_": 851242077,
    "aziatov": 138349349,
    "nice_korew25": 140821964,
}

def format_player_html(name: str) -> str:
    """
    Возвращает HTML-ссылку на профиль Telegram или просто имя.
    """
    user_id = PLAYER_ID_MAP.get(name)
    safe_name = escape(name)
    if user_id:
        return f'<a href="tg://user?id={user_id}">{safe_name}</a>'
    return safe_name


@dataclass
class ServerStatus:
    """Состояние сервера"""
    state: ServerState
    ip: Optional[str] = None
    uptime: Optional[str] = None
    minecraft_active: bool = False
    players: int = 0
    max_players: int = 20
    names: Optional[List[str]] = None

    @staticmethod
    def format_server_status(status: 'ServerStatus', monitoring_enabled: bool) -> str:
        """Форматирует статус сервера для отображения"""
        state_emoji = {
            ServerState.OFF: "⚫",
            ServerState.STARTING: "🟡",
            ServerState.BOOTING: "🟠",
            ServerState.READY: "🟢"
        }

        state_text = {
            ServerState.OFF: "Выключен",
            ServerState.STARTING: "Запускается",
            ServerState.BOOTING: "VPS включен",
            ServerState.READY: "Работает"
        }

        emoji = state_emoji.get(status.state, "⚪")
        text = state_text.get(status.state, "Неизвестно")

        result = f"{emoji} <b>VPS Status:</b> {text}\n"

        if status.ip:
            result += f"🌐 <b>IP:</b> <code>{status.ip}</code>\n"

        if status.uptime:
            result += f"⏱️ <b>Uptime:</b> {status.uptime}\n"
        else:
            result += f"⏱️ <b>Uptime:</b> N/A\n"

        if status.state == ServerState.READY and status.minecraft_active:
            result += f"\n🎮 <b>Minecraft:</b> Активен\n"
            result += f"👥 <b>Игроков:</b> {status.players}/{status.max_players}"

            if status.names and len(status.names) > 0:
                result += f"\n📋 <b>Онлайн:</b> {', '.join(status.names)}"
        else:
            result += f"\n🎮 <b>Minecraft:</b> Не запущен"

        result += "Бот:\n"
        result += (
            "🟢 <b>Автовыключение:</b> Включено"
            if monitoring_enabled
            else "🔴 <b>Автовыключение:</b> Выключено"
        )

        return result

    @staticmethod
    def format_players(status: 'ServerStatus') -> str:
        """Форматирует информацию об игроках"""
        if status.state != ServerState.READY or not status.minecraft_active:
            return "🎮 Сервер не запущен"

        result = f"👥 <b>Игроков онлайн:</b> {status.players}/{status.max_players}\n"

        if status.names and len(status.names) > 0:
            result += f"\n📋 <b>Список игроков:</b>\n"
            for i, name in enumerate(status.names, 1):
                result += f"{i}. {name}\n"
        else:
            result += "\n🚫 Никого нет онлайн"

        if status.ip:
            result += f"\n🌐 <b>IP сервера:</b> <code>{status.ip}</code>"

        return result