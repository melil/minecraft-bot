import asyncio
import logging
import re
from typing import Tuple, Optional, List
from core.config import MINECRAFT_RCON_PASSWORD

from core.ssh.client import SSHClient

logger = logging.getLogger(__name__)

# Константа с путем к Minecraft (на основе ваших данных)
MINECRAFT_DIR = "/root/freshcraft_industrial_server"


async def is_ready(ssh_config: dict) -> bool:
    """
    Проверяет, готов ли Minecraft сервер через systemd
    """
    try:
        client = SSHClient(**ssh_config)
        result = await client.execute(
            "systemctl is-active minecraft.service 2>/dev/null || echo 'inactive'",
            timeout=10
        )
        is_active = result.strip() == "active"
        logger.debug(f"Minecraft systemd status: {result.strip()}")
        return is_active
    except Exception as e:
        logger.error(f"Ошибка проверки статуса Minecraft: {e}")
        return False


async def get_players_via_rcon(client: SSHClient) -> Tuple[Optional[int], Optional[int], Optional[List[str]]]:
    try:
        result = await client.execute(
            f"mcrcon -H 127.0.0.1 -P 25575 -p '{MINECRAFT_RCON_PASSWORD}' list 2>&1",
            timeout=10
        )

        logger.debug(f"RCON raw response: {result}")

        if "There are" in result:
            lines = result.strip().split('\n')
            for line in lines:
                if "There are" in line:
                    # Паттерн: "There are 2 of a max of 20 players online: Trudovick, aziatov"
                    match = re.search(r'There are (\d+) of a max of (\d+) players online', line)
                    if match:
                        current = int(match.group(1))
                        maximum = int(match.group(2))

                        # Ищем имена после двоеточия
                        if ':' in line and current > 0:
                            names_part = line.split(':', 1)[1].strip()
                            names = [n.strip() for n in names_part.split(',') if n.strip()]
                            logger.info(f"✅ RCON: {current}/{maximum} игроков: {names}")
                            return current, maximum, names

                        logger.info(f"✅ RCON: {current}/{maximum} игроков")
                        return current, maximum, None

        logger.warning(f"RCON ответ не содержит данных: {result[:200]}")
        return None, None, None

    except Exception as e:
        logger.debug(f"RCON не доступен: {e}")
        return None, None, None

async def get_players_via_logs(client: SSHClient) -> Tuple[int, int, Optional[List[str]]]:
    """
    Получает список игроков из логов journalctl
    """
    try:
        # Получаем события входа/выхода за последние 3 часа
        result = await client.execute(
            "journalctl -u minecraft.service --since '3 hours ago' --no-pager 2>/dev/null | "
            "grep -iE 'joined the game|left the game' | tail -100 || echo ''",
            timeout=15
        )

        online_players = set()

        if result:
            for line in result.split('\n'):
                # Паттерны для Forge/Vanilla:
                # [12:34:56] [Server thread/INFO]: Steve joined the game
                # [12:34:56] [Server thread/INFO] [minecraft/DedicatedServer]: Steve joined the game

                if 'joined the game' in line.lower():
                    # Ищем имя перед "joined"
                    match = re.search(r':\s*(\w+)\s+joined the game', line, re.IGNORECASE)
                    if match:
                        player_name = match.group(1)
                        online_players.add(player_name)
                        logger.debug(f"Игрок вошел: {player_name}")

                elif 'left the game' in line.lower():
                    match = re.search(r':\s*(\w+)\s+left the game', line, re.IGNORECASE)
                    if match:
                        player_name = match.group(1)
                        online_players.discard(player_name)
                        logger.debug(f"Игрок вышел: {player_name}")

        count = len(online_players)
        names = sorted(list(online_players)) if online_players else None

        if count > 0:
            logger.info(f"Логи: {count} игроков онлайн: {names}")
        else:
            logger.debug("Логи: игроков не найдено")

        return count, 20, names

    except Exception as e:
        logger.debug(f"Парсинг логов не удался: {e}")
        return 0, 20, None


async def get_players_via_connections(client: SSHClient) -> int:
    """
    Подсчитывает игроков по активным TCP соединениям к порту 25565

    Самый надежный метод, работает всегда
    """
    try:
        result = await client.execute(
            "ss -tn 2>/dev/null | grep ':25565' | grep ESTAB | wc -l || echo '0'",
            timeout=10
        )

        count = int(result.strip()) if result.strip().isdigit() else 0

        if count > 0:
            logger.info(f"TCP: {count} активных соединений")
        else:
            logger.debug("TCP: нет активных соединений")

        return count

    except Exception as e:
        logger.debug(f"Подсчет соединений не удался: {e}")
        return 0


async def players_with_names_count(ssh_config: dict) -> Tuple[int, int, Optional[List[str]]]:
    """
    Получает количество игроков и их имена используя несколько методов

    Приоритет методов:
    1. RCON (точный, с именами)
    2. Логи (достаточно точный, с именами)
    3. TCP соединения (точный счет, без имен)
    """
    try:
        client = SSHClient(**ssh_config)

        # Метод 1: RCON (самый точный)
        logger.debug("Попытка получить данные через RCON...")
        players, max_players, names = await get_players_via_rcon(client)

        if players is not None:
            return players, max_players, names

        # Метод 2: Логи journalctl
        logger.debug("Попытка получить данные из логов...")
        players, max_players, names = await get_players_via_logs(client)

        if players > 0 or names:
            return players, max_players, names

        # Метод 3: TCP соединения (fallback, всегда работает)
        logger.debug("Использую TCP соединения...")
        players = await get_players_via_connections(client)

        if players > 0:
            logger.info(f"✅ Определено {players} игроков через TCP")
            return players, 20, None

        # Если все методы вернули 0
        logger.debug("Все методы показали 0 игроков")
        return 0, 20, None

    except Exception as e:
        logger.error(f"Ошибка получения информации об игроках: {e}")
        return 0, 20, None


async def players_count(ssh_config: dict) -> int:
    """
    Получает только количество игроков (быстрый метод)
    """
    players, _, _ = await players_with_names_count(ssh_config)
    return players


async def get_minecraft_status(ssh_config: dict) -> dict:
    """
    Получает полный статус Minecraft сервера

    Returns:
        {
            'active': bool,           # Запущен ли сервер
            'players': int,           # Количество игроков
            'max_players': int,       # Максимум игроков
            'names': List[str]|None   # Список имен (если доступно)
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