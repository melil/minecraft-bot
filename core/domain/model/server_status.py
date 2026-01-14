# core/domain/model/server_status.py
from dataclasses import dataclass
from typing import Optional, TYPE_CHECKING

from core.domain.model.server_state import ServerState

if TYPE_CHECKING:
    pass


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

    def format_players(self: 'ServerStatus') -> str:  # Или укажи как строку
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
                lines = [f"👥 Игроков онлайн: {self.players} / {self.max_players}"]
                if self.players > 0:
                    lines.append(f"\n{self.names}")


                return "\n".join(lines)

            case ServerState.ERROR:
                return "❌ Ошибка определения состояния"

            case _:
                return "❓ Неизвестное состояние"

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
                lines = ["☁️ *VPS запущен*", "\n⛏️ *Minecraft*:"]

                if self.minecraft_active:
                    lines.append("🟢 Сервер активен")

                if self.players >= 0:
                    lines.append(f"👥 Игроков онлайн: {self.players}")

                lines.append("\n☁️ *VPS*:")
                if self.ip:
                    lines.append(f"🌍 IP: `{self.ip}`")

                if self.ram:
                    lines.append(f"⚡️ RAM: {self.ram} MB")

                if self.disk:
                    lines.append(f"💾 Disk: {self.disk} GB")

                if self.balance:
                    lines.append(f"💰 Баланс: {self.balance} ₽")

                return "\n".join(lines)

            case ServerState.ERROR:
                return "❌ Ошибка определения состояния"

            case _:
                return "❓ Неизвестное состояние"