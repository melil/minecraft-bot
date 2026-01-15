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


async def get_players_via_rcon(client: SSHClient) -> Tuple[int, int, Optional[List[str]]]:
    """
    Получает список игроков через RCON
    """
    try:
        # Пробуем mcrcon
        result = await client.execute(
            "mcrcon -H 127.0.0.1 -P 25575 -p $(grep 'rcon.password' /root/freshcraft_industrial_server/server.properties | cut -d= -f2 || echo 'minecraft') list 2>/dev/null",
            timeout=10
        )

        if "There are" in result:
            # Парсим: "There are 2 of a max of 20 players online: Steve, Alex"
            lines = result.strip().split('\n')
            for line in lines:
                if "There are" in line:
                    match = re.search(r'There are (\d+) of a max of (\d+) players online', line)
                    if match:
                        current = int(match.group(1))
                        maximum = int(match.group(2))

                        # Ищем список имен после двоеточия
                        if ':' in line and current > 0:
                            names_part = line.split(':', 1)[1].strip()
                            names = [n.strip() for n in names_part.split(',') if n.strip()]
                            return current, maximum, names

                        return current, maximum, None

        return None, None, None

    except Exception as e:
        logger.debug(f"RCON не доступен: {e}")
        return None, None, None


async def get_players_via_logs(client: SSHClient) -> Tuple[int, int, Optional[List[str]]]:
    """
    Получает список игроков из логов journalctl
    """
    try:
        # Получаем события входа/выхода за последний час
        result = await client.execute(
            "journalctl -u minecraft.service --since '1 hour ago' --no-pager 2>/dev/null | "
            "grep -E 'joined the game|left the game' || echo ''",
            timeout=15
        )

        online_players = set()

        if result:
            for line in result.split('\n'):
                # Паттерн: "[14:30:25] [Server thread/INFO]: Steve joined the game"
                if 'joined the game' in line.lower():
                    # Ищем имя перед "joined"
                    match = re.search(r':\s*(\w+)\s+joined the game', line, re.IGNORECASE)
                    if match:
                        player_name = match.group(1)
                        online_players.add(player_name)

                elif 'left the game' in line.lower():
                    match = re.search(r':\s*(\w+)\s+left the game', line, re.IGNORECASE)
                    if match:
                        player_name = match.group(1)
                        online_players.discard(player_name)

        count = len(online_players)
        names = sorted(list(online_players)) if online_players else None

        return count, 20, names

    except Exception as e:
        logger.debug(f"Парсинг логов не удался: {e}")
        return 0, 20, None


async def get_players_via_connections(client: SSHClient) -> int:
    """
    Подсчитывает игроков по активным TCP соединениям к порту 25565
    """
    try:
        result = await client.execute(
            "ss -tn 2>/dev/null | grep ':25565' | grep ESTAB | wc -l || echo '0'",
            timeout=10
        )

        count = int(result.strip()) if result.strip().isdigit() else 0
        return count

    except Exception as e:
        logger.debug(f"Подсчет соединений не удался: {e}")
        return 0


async def players_with_names_count(ssh_config: dict) -> Tuple[int, int, Optional[List[str]]]:
    """
    Получает количество игроков и их имена используя несколько методов
    """
    try:
        client = SSHClient(**ssh_config)

        # Метод 1: RCON (самый точный)
        logger.debug("Попытка получить данные через RCON...")
        players, max_players, names = await get_players_via_rcon(client)

        if players is not None:
            logger.debug(f"✅ RCON: {players}/{max_players} игроков, имена: {names}")
            return players, max_players, names

        # Метод 2: Логи journalctl
        logger.debug("Попытка получить данные из логов...")
        players, max_players, names = await get_players_via_logs(client)

        if players > 0 or names:
            logger.debug(f"✅ Логи: {players}/{max_players} игроков, имена: {names}")
            return players, max_players, names

        # Метод 3: TCP соединения (без имен)
        logger.debug("Попытка подсчитать TCP соединения...")
        players = await get_players_via_connections(client)

        if players > 0:
            logger.debug(f"✅ TCP: {players} соединений")
            return players, 20, None

        # Если все методы вернули 0
        logger.debug("Все методы вернули 0 игроков")
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