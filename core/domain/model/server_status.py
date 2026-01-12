# core/domain/model/server_status.py
from dataclasses import dataclass
from typing import Optional, TYPE_CHECKING

from core.domain.model.server_state import ServerState

if TYPE_CHECKING:
    pass


@dataclass
class ServerStatus:
    state: ServerState
    players: int = -1
    ip: Optional[str] = None

    def format_server_status(self: 'ServerStatus') -> str:  # Или укажи как строку
        match self.state:
            case ServerState.OFF:
                return "⛔ Сервер выключен"

            case ServerState.STARTING:
                return "☁️ VPS запускается\n🎮 Minecraft: ⏳ ожидается"

            case ServerState.BOOTING:
                return "☁️ VPS: ✅ запущен\n🎮 Minecraft загружается"

            case ServerState.READY:
                lines = ["🎮 Сервер готов, можно заходить"]

                if self.players >= 0:
                    lines.append(f"👥 Игроков онлайн: {self.players}")

                if self.ip:
                    lines.append(f"🌍 IP: `{self.ip}`")

                return "\n".join(lines)

            case ServerState.ERROR:
                return "❌ Ошибка определения состояния"

            case _:
                return "❓ Неизвестное состояние"