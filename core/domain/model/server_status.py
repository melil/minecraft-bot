# core/domain/model/server_status.py
from dataclasses import dataclass
from typing import Optional, TYPE_CHECKING
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
    state: ServerState
    players: int = -1,
    max_players: int = -1,
    names: list[str] = None
    ip: Optional[str] = None,
    minecraft_active: bool = False,
    balance: Optional[str] = None,
    ram: Optional[str] = None,
    disk: Optional[str] = None,

    def format_players(self: 'ServerStatus') -> str:
        match self.state:
            case ServerState.OFF:
                return "⛔ Сервер выключен"

            case ServerState.STARTING:
                return "☁️ VPS запускается\n🎮 Minecraft: ⏳ ожидается"

            case ServerState.BOOTING:
                return "☁️ VPS: ✅ запущен\n🎮 Minecraft загружается"

            case ServerState.READY:
                lines = [f"👥 Игроков онлайн: {self.players} / {self.max_players}"]
                if self.names:
                    player_links = [format_player_html(name) for name in self.names]
                    lines.append(", ".join(player_links))
                return "\n".join(lines)  # <- используем \n, НЕ <br>

            case ServerState.ERROR:
                return "❌ Ошибка определения состояния"

            case _:
                return "❓ Неизвестное состояние"

    def format_server_status(self: 'ServerStatus') -> str:
        match self.state:
            case ServerState.OFF:
                return "⛔ Сервер выключен"

            case ServerState.STARTING:
                return "☁️ VPS запускается\n🎮 Minecraft: ⏳ ожидается"

            case ServerState.BOOTING:
                return "☁️ VPS: ✅ запущен\n🎮 Minecraft загружается"

            case ServerState.READY:
                lines = ["☁️ <b>VPS запущен</b>", "⛏️ <b>Minecraft</b>"]

                if self.minecraft_active:
                    lines.append("🟢 Сервер активен")

                if self.players >= 0:
                    lines.append(f"👥 Игроков онлайн: {self.players} / {self.max_players}")
                    if self.names:
                        player_links = [format_player_html(name) for name in self.names]
                        lines.append(", ".join(player_links))

                lines.append("☁️ <b>VPS</b>:")
                if self.ip:
                    lines.append(f"🌍 IP: <code>{escape(self.ip)}</code>")

                if self.ram:
                    lines.append(f"⚡️ RAM: {self.ram} MB")

                if self.disk:
                    lines.append(f"💾 Disk: {self.disk} GB")

                if self.balance:
                    lines.append(f"💰 Баланс: {self.balance} ₽")

                return "\n".join(lines)  # <- \n вместо <br>

            case ServerState.ERROR:
                return "❌ Ошибка определения состояния"

            case _:
                return "❓ Неизвестное состояние"
