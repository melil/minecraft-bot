import asyncio
import logging
import re
from typing import Tuple, Optional, List

from core.ssh.client import SSHClient

logger = logging.getLogger(__name__)


async def is_ready(ssh_config: dict) -> bool:
    """
    Проверяет, готов ли Minecraft сервер через systemd
    """
    try:
        client = SSHClient(**ssh_config)
        result = await client.execute("systemctl is-active minecraft.service || echo 'inactive'", timeout=10)
        is_active = result.strip() == "active"
        logger.debug(f"Minecraft systemd status: {result.strip()}")
        return is_active
    except Exception as e:
        logger.error(f"Ошибка проверки статуса Minecraft: {e}")
        return False


async def players_count(ssh_config: dict) -> int:
    """
    Получает количество игроков из логов journalctl
    """
    try:
        client = SSHClient(**ssh_config)

        # Ищем последнее упоминание количества игроков в логах
        result = await client.execute(
            "journalctl -u minecraft.service --since '10 minutes ago' --no-pager 2>/dev/null | "
            "grep -i 'UUID of player' | wc -l || echo '0'",
            timeout=15
        )

        count = 0
        if result and result.strip().isdigit():
            count = int(result.strip())

        logger.debug(f"Игроков онлайн (из логов): {count}")
        return count

    except Exception as e:
        logger.error(f"Ошибка получения количества игроков: {e}")
        return 0


async def players_with_names_count(ssh_config: dict) -> Tuple[int, int, Optional[List[str]]]:
    """
    Получает количество игроков и их имена из логов
    """
    try:
        client = SSHClient(**ssh_config)

        # Получаем события входа/выхода за последние 30 минут
        result = await client.execute(
            "journalctl -u minecraft.service --since '30 minutes ago' --no-pager 2>/dev/null | "
            "grep -E 'joined the game|left the game' | tail -50 || echo ''",
            timeout=15
        )

        # Парсим имена игроков
        online_players = set()

        if result:
            for line in result.split('\n'):
                # Паттерн: "player_name joined the game"
                if 'joined the game' in line.lower():
                    match = re.search(r'(\w+)\s+joined the game', line, re.IGNORECASE)
                    if match:
                        player_name = match.group(1)
                        online_players.add(player_name)
                        logger.debug(f"Игрок вошел: {player_name}")

                # Паттерн: "player_name left the game"
                elif 'left the game' in line.lower():
                    match = re.search(r'(\w+)\s+left the game', line, re.IGNORECASE)
                    if match:
                        player_name = match.group(1)
                        online_players.discard(player_name)
                        logger.debug(f"Игрок вышел: {player_name}")

        players_count = len(online_players)
        names_list = sorted(list(online_players)) if online_players else None

        logger.debug(f"Игроков онлайн: {players_count}, Имена: {names_list}")
        return players_count, 20, names_list

    except Exception as e:
        logger.error(f"Ошибка получения информации об игроках: {e}")
        return 0, 20, None


async def get_minecraft_status(ssh_config: dict) -> dict:
    """
    Получает полный статус Minecraft сервера

    Returns:
        {
            'active': bool,         # Запущен ли сервер
            'players': int,         # Количество игроков
            'max_players': int,     # Максимум игроков
            'names': List[str]|None # Список имен игроков
        }
    """
    # Проверяем, запущен ли сервер
    active = await is_ready(ssh_config)

    if not active:
        logger.debug("Minecraft сервер не активен")
        return {
            'active': False,
            'players': 0,
            'max_players': 20,
            'names': None
        }

    # Получаем информацию об игроках
    players, max_players, names = await players_with_names_count(ssh_config)

    return {
        'active': True,
        'players': players,
        'max_players': max_players,
        'names': names or []
    }