import asyncio
import logging
from typing import Tuple, Optional, List

from core.ssh.client import SSHClient
from core.config import MINECRAFT_SERVER_SSH

logger = logging.getLogger(__name__)


async def is_ready(ssh_config: dict) -> bool:
    """
    Проверяет, готов ли Minecraft сервер к подключению
    """
    try:
        client = SSHClient(**ssh_config)
        result = await client.execute("systemctl is-active minecraft.service")
        is_active = result.strip() == "active"
        logger.debug(f"Minecraft service active: {is_active}")
        return is_active
    except Exception as e:
        logger.error(f"Ошибка проверки готовности Minecraft: {e}")
        return False


async def players_count(ssh_config: dict) -> int:
    """
    Получает количество игроков онлайн
    """
    try:
        client = SSHClient(**ssh_config)
        result = await client.execute(
            "tmux send-keys -t minecraft 'list' C-m && sleep 0.5 && "
            "tmux capture-pane -t minecraft -p | grep 'There are' | tail -1"
        )

        if "There are" in result:
            # Формат: "There are 2 of a max of 20 players online:"
            parts = result.split()
            if len(parts) >= 3:
                count = int(parts[2])
                logger.debug(f"Players online: {count}")
                return count

        logger.debug("No players online")
        return 0
    except Exception as e:
        logger.error(f"Ошибка получения количества игроков: {e}")
        return 0


async def players_with_names_count(ssh_config: dict) -> Tuple[int, int, Optional[List[str]]]:
    """
    Получает количество игроков, максимум и список имен

    Returns:
        Tuple[int, int, Optional[List[str]]]: (текущие игроки, максимум, список имен)
    """
    try:
        client = SSHClient(**ssh_config)
        result = await client.execute(
            "tmux send-keys -t minecraft 'list' C-m && sleep 0.5 && "
            "tmux capture-pane -t minecraft -p | grep -A 1 'There are' | tail -2"
        )

        lines = result.strip().split('\n')
        players = 0
        max_players = 20
        names = None

        for line in lines:
            if "There are" in line:
                # "There are 2 of a max of 20 players online:"
                parts = line.split()
                if len(parts) >= 3:
                    players = int(parts[2])
                if len(parts) >= 7:
                    max_players = int(parts[6])
            elif line.strip() and "There are" not in line:
                # Список игроков через запятую
                names = [name.strip() for name in line.split(',') if name.strip()]

        logger.debug(f"Players: {players}/{max_players}, Names: {names}")
        return players, max_players, names
    except Exception as e:
        logger.error(f"Ошибка получения информации об игроках: {e}")
        return 0, 20, None


# ==================== ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ ====================

async def get_minecraft_status(ssh_config: dict) -> dict:
    """
    Получает полный статус Minecraft сервера

    Returns:
        dict: {
            'active': bool,
            'players': int,
            'max_players': int,
            'names': List[str] | None
        }
    """
    active = await is_ready(ssh_config)

    if not active:
        return {
            'active': False,
            'players': 0,
            'max_players': 20,
            'names': None
        }

    players, max_players, names = await players_with_names_count(ssh_config)

    return {
        'active': True,
        'players': players,
        'max_players': max_players,
        'names': names or []
    }