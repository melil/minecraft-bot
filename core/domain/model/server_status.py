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
    ip: Optional[str] = None,
    minecraft_active: bool = False,
    balance: Optional[str] = None,
    ram: Optional[str] = None,
    disk: Optional[str] = None,


    def format_server_status(self: 'ServerStatus') -> str:  # Или укажи как строку
        match self.state:
            case ServerState.OFF:
                print("⛔ Сервер выключен")
                return "⛔ Сервер выключен"

            case ServerState.STARTING:
                print("☁️ VPS запускается\n🎮 Minecraft: ⏳ ожидается")
                return "☁️ VPS запускается\n🎮 Minecraft: ⏳ ожидается"

            case ServerState.BOOTING:
                print("☁️ VPS: ✅ запущен\n🎮 Minecraft загружается")
                return "☁️ VPS: ✅ запущен\n🎮 Minecraft загружается"

            case ServerState.READY:
                lines = ["☁️ VPS запущен", f"\n ⛏️ Minecraft:"]

                if self.minecraft_active:
                    lines.append(f"🟢 Сервер активен")

                if self.players >= 0:
                    lines.append(f"👥 Игроков онлайн: {self.players}")

                lines.append(f"\n ☁️ VPS:")
                if self.ip:
                    lines.append(f"🌍 IP: `{self.ip}`")

                if self.ram:
                    lines.append(f"⚡️ RAM: `{self.ram}`")

                if self.disk:
                    lines.append(f"💾 Disk: `{self.ram}`")

                if self.balance:
                    lines.append(f"💰 Баланс: {self.balance} ₽")

                return "\n".join(lines)

            case ServerState.ERROR:
                return "❌ Ошибка определения состояния"

            case _:
                return "❓ Неизвестное состояние"