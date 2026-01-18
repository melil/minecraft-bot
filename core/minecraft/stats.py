"""
Модуль для работы со статистикой игроков Minecraft
Читает файлы статистики из world/stats/UUID.json через SSH
"""
import asyncio
import json
import logging
import re
from datetime import datetime, timedelta
from typing import Optional, Dict, List, Tuple
from core.ssh.client import SSHClient

logger = logging.getLogger(__name__)

# Константа с путем к Minecraft (используется из service.py)
MINECRAFT_DIR = "/root/freshcraft_industrial_server"

# Константы для преобразования
TICKS_PER_SECOND = 20
SECONDS_PER_MINUTE = 60
MINUTES_PER_HOUR = 60
HOURS_PER_DAY = 24


def ticks_to_timedelta(ticks: int) -> timedelta:
    """
    Преобразует тики Minecraft в timedelta
    
    Args:
        ticks: количество игровых тиков (20 тиков = 1 секунда)
    
    Returns:
        timedelta объект
    """
    seconds = ticks / TICKS_PER_SECOND
    return timedelta(seconds=seconds)


def format_playtime(td: timedelta) -> str:
    """
    Форматирует timedelta в читаемую строку
    
    Args:
        td: timedelta объект
    
    Returns:
        Строка вида "X дней Y часов Z минут" или "X часов Y минут"
    """
    total_seconds = int(td.total_seconds())
    
    days = total_seconds // (SECONDS_PER_MINUTE * MINUTES_PER_HOUR * HOURS_PER_DAY)
    hours = (total_seconds % (SECONDS_PER_MINUTE * MINUTES_PER_HOUR * HOURS_PER_DAY)) // (SECONDS_PER_MINUTE * MINUTES_PER_HOUR)
    minutes = (total_seconds % (SECONDS_PER_MINUTE * MINUTES_PER_HOUR)) // SECONDS_PER_MINUTE
    
    parts = []
    if days > 0:
        parts.append(f"{days} д.")
    if hours > 0:
        parts.append(f"{hours} ч.")
    if minutes > 0 or not parts:  # Показываем минуты если это единственное значение
        parts.append(f"{minutes} мин.")
    
    return " ".join(parts)


async def get_usercache(ssh_config: dict) -> Dict[str, str]:
    """
    Читает usercache.json с сервера для маппинга UUID -> nickname
    
    Args:
        ssh_config: конфигурация SSH
    
    Returns:
        Словарь {uuid: nickname}
    """
    try:
        client = SSHClient(**ssh_config)
        result = await client.execute(
            f"cat {MINECRAFT_DIR}/usercache.json 2>/dev/null || echo '[]'",
            timeout=10
        )
        
        if not result or result.strip() == '[]':
            logger.warning("usercache.json пуст или не найден")
            return {}
        
        usercache = json.loads(result)
        
        # Создаем маппинг uuid -> name
        uuid_map = {}
        for entry in usercache:
            if 'uuid' in entry and 'name' in entry:
                # UUID в usercache хранится с дефисами
                uuid_str = entry['uuid'].lower()
                uuid_map[uuid_str] = entry['name']
        
        logger.info(f"Загружено {len(uuid_map)} записей из usercache.json")
        return uuid_map
        
    except Exception as e:
        logger.error(f"Ошибка чтения usercache.json: {e}")
        return {}


async def uuid_to_username(ssh_config: dict, player_uuid: str, usercache: Optional[Dict[str, str]] = None) -> str:
    """
    Преобразует UUID игрока в никнейм
    
    Args:
        ssh_config: конфигурация SSH
        player_uuid: UUID игрока (с или без дефисов)
        usercache: опциональный предзагруженный кэш
    
    Returns:
        Никнейм игрока или UUID если не найден
    """
    try:
        # Нормализуем UUID (убираем дефисы и приводим к нижнему регистру)
        uuid_normalized = player_uuid.replace('-', '').lower()
        
        # Добавляем дефисы в стандартном формате если их нет
        if len(uuid_normalized) == 32:
            uuid_with_dashes = f"{uuid_normalized[:8]}-{uuid_normalized[8:12]}-{uuid_normalized[12:16]}-{uuid_normalized[16:20]}-{uuid_normalized[20:]}"
        else:
            uuid_with_dashes = player_uuid.lower()
        
        # Если кэш не предоставлен, загружаем
        if usercache is None:
            usercache = await get_usercache(ssh_config)
        
        # Ищем в кэше
        if uuid_with_dashes in usercache:
            return usercache[uuid_with_dashes]
        
        # Если не нашли, возвращаем первые 8 символов UUID
        logger.warning(f"Никнейм для UUID {player_uuid} не найден")
        return uuid_normalized[:8]
        
    except Exception as e:
        logger.error(f"Ошибка преобразования UUID {player_uuid}: {e}")
        return player_uuid[:8]


async def get_player_stats_raw(ssh_config: dict, player_uuid: str) -> Optional[dict]:
    """
    Читает сырые данные статистики игрока из файла
    
    Args:
        ssh_config: конфигурация SSH
        player_uuid: UUID игрока (имя файла без .json)
    
    Returns:
        Словарь со статистикой или None при ошибке
    """
    try:
        client = SSHClient(**ssh_config)
        
        # Читаем файл статистики
        result = await client.execute(
            f"cat {MINECRAFT_DIR}/world/stats/{player_uuid}.json 2>/dev/null || echo ''",
            timeout=10
        )
        
        if not result or result.strip() == '':
            logger.warning(f"Файл статистики для {player_uuid} не найден")
            return None
        
        stats_data = json.loads(result)
        return stats_data
        
    except json.JSONDecodeError as e:
        logger.error(f"Ошибка парсинга JSON для {player_uuid}: {e}")
        return None
    except Exception as e:
        logger.error(f"Ошибка чтения статистики для {player_uuid}: {e}")
        return None


async def get_player_playtime(ssh_config: dict, player_uuid: str) -> Optional[int]:
    """
    Получает время игры игрока в тиках
    
    Args:
        ssh_config: конфигурация SSH
        player_uuid: UUID игрока
    
    Returns:
        Время в тиках или None при ошибке
    """
    stats = await get_player_stats_raw(ssh_config, player_uuid)
    
    if not stats:
        return None
    
    try:
        # Путь к play_time: stats -> minecraft:custom -> minecraft:play_time
        custom_stats = stats.get('stats', {}).get('minecraft:custom', {})
        playtime_ticks = custom_stats.get('minecraft:play_time', 0)
        
        return playtime_ticks
        
    except Exception as e:
        logger.error(f"Ошибка извлечения playtime для {player_uuid}: {e}")
        return None


async def get_player_stats(ssh_config: dict, player_uuid: str, nickname: Optional[str] = None) -> Optional[dict]:
    """
    Получает полную статистику игрока
    
    Args:
        ssh_config: конфигурация SSH
        player_uuid: UUID игрока
        nickname: опциональный никнейм (если уже известен)
    
    Returns:
        Словарь со статистикой или None
    """
    stats = await get_player_stats_raw(ssh_config, player_uuid)
    
    if not stats:
        return None
    
    try:
        # Получаем никнейм если не предоставлен
        if nickname is None:
            nickname = await uuid_to_username(ssh_config, player_uuid)
        
        # Извлекаем основные метрики
        custom_stats = stats.get('stats', {}).get('minecraft:custom', {})
        
        playtime_ticks = custom_stats.get('minecraft:play_time', 0)
        deaths = custom_stats.get('minecraft:deaths', 0)
        jumps = custom_stats.get('minecraft:jump', 0)
        
        # Дополнительные метрики
        killed_stats = stats.get('stats', {}).get('minecraft:killed', {})
        killed_by_stats = stats.get('stats', {}).get('minecraft:killed_by', {})
        mined_stats = stats.get('stats', {}).get('minecraft:mined', {})
        
        mob_kills = sum(killed_stats.values())
        blocks_mined = sum(mined_stats.values())
        
        # Урон
        damage_dealt = custom_stats.get('minecraft:damage_dealt', 0)
        damage_taken = custom_stats.get('minecraft:damage_taken', 0)
        
        return {
            'uuid': player_uuid,
            'nickname': nickname,
            'playtime_ticks': playtime_ticks,
            'playtime': ticks_to_timedelta(playtime_ticks),
            'playtime_formatted': format_playtime(ticks_to_timedelta(playtime_ticks)),
            'deaths': deaths,
            'mob_kills': mob_kills,
            'jumps': jumps,
            'blocks_mined': blocks_mined,
            'damage_dealt': damage_dealt,
            'damage_taken': damage_taken,
            # Детальная статистика для расширенного просмотра
            'killed_detailed': killed_stats,
            'killed_by_detailed': killed_by_stats,
            'mined_detailed': mined_stats,
        }
        
    except Exception as e:
        logger.error(f"Ошибка обработки статистики для {player_uuid}: {e}")
        return None


async def get_all_players_list(ssh_config: dict) -> List[str]:
    """
    Получает список всех UUID игроков на сервере
    
    Args:
        ssh_config: конфигурация SSH
    
    Returns:
        Список UUID (без расширения .json)
    """
    try:
        client = SSHClient(**ssh_config)
        
        # Получаем список файлов статистики
        result = await client.execute(
            f"ls {MINECRAFT_DIR}/world/stats/*.json 2>/dev/null | xargs -n1 basename -s .json || echo ''",
            timeout=15
        )
        
        if not result or result.strip() == '':
            logger.warning("Не найдено файлов статистики")
            return []
        
        uuids = [line.strip() for line in result.strip().split('\n') if line.strip()]
        logger.info(f"Найдено {len(uuids)} игроков")
        
        return uuids
        
    except Exception as e:
        logger.error(f"Ошибка получения списка игроков: {e}")
        return []


async def get_all_players_stats(ssh_config: dict, limit: Optional[int] = None) -> List[dict]:
    """
    Получает статистику всех игроков на сервере
    
    Args:
        ssh_config: конфигурация SSH
        limit: опциональное ограничение количества игроков
    
    Returns:
        Список словарей со статистикой
    """
    try:
        # Получаем список UUID
        uuids = await get_all_players_list(ssh_config)
        
        if not uuids:
            return []
        
        # Ограничиваем количество если указано
        if limit:
            uuids = uuids[:limit]
        
        # Загружаем usercache один раз для всех
        usercache = await get_usercache(ssh_config)
        
        # Собираем статистику для каждого игрока
        all_stats = []
        for uuid in uuids:
            nickname = await uuid_to_username(ssh_config, uuid, usercache)
            player_stats = await get_player_stats(ssh_config, uuid, nickname)
            
            if player_stats:
                all_stats.append(player_stats)
        
        logger.info(f"Загружена статистика для {len(all_stats)} игроков")
        return all_stats
        
    except Exception as e:
        logger.error(f"Ошибка получения статистики всех игроков: {e}")
        return []


async def get_top_players_by_playtime(ssh_config: dict, limit: int = 10, force_reload: bool = False) -> List[dict]:
    """
    Получает топ игроков по времени игры
    
    Args:
        ssh_config: конфигурация SSH
        limit: количество игроков в топе
        force_reload: принудительная загрузка с сервера (игнорирует кэш)
    
    Returns:
        Отсортированный список игроков
    """
    try:
        # Всегда загружаем ВСЕ игроки с сервера для точного топа
        logger.info(f"🔄 Загрузка статистики всех игроков для топа (force_reload={force_reload})")
        all_stats = await get_all_players_stats(ssh_config, limit=None)
        
        if not all_stats:
            logger.warning("❌ Не удалось загрузить статистику игроков")
            return []
        
        logger.info(f"📊 Загружено игроков: {len(all_stats)}")
        
        # Сортируем по времени игры (убывание)
        sorted_stats = sorted(
            all_stats,
            key=lambda x: x.get('playtime_ticks', 0),
            reverse=True
        )
        
        # Логируем топ для отладки
        logger.info(f"🏆 Топ-{min(limit, len(sorted_stats))} игроков:")
        for i, player in enumerate(sorted_stats[:limit], 1):
            logger.info(f"  {i}. {player['nickname']:15s} - {player['playtime_ticks']:10d} ticks ({player['playtime_formatted']})")
        
        return sorted_stats[:limit]
        
    except Exception as e:
        logger.error(f"Ошибка получения топа игроков: {e}", exc_info=True)
        return []


async def find_player_by_nickname(ssh_config: dict, nickname: str) -> Optional[Tuple[str, str]]:
    """
    Ищет UUID игрока по никнейму
    
    Args:
        ssh_config: конфигурация SSH
        nickname: никнейм игрока (регистронезависимый)
    
    Returns:
        Кортеж (uuid, точный_никнейм) или None если не найден
    """
    try:
        usercache = await get_usercache(ssh_config)
        
        nickname_lower = nickname.lower()
        
        for uuid, name in usercache.items():
            if name.lower() == nickname_lower:
                return (uuid, name)
        
        logger.warning(f"Игрок {nickname} не найден в usercache")
        return None
        
    except Exception as e:
        logger.error(f"Ошибка поиска игрока {nickname}: {e}")
        return None


def format_detailed_stats(detailed_dict: dict, category: str, limit: int = 10) -> str:
    """
    Форматирует детальную статистику в читаемый вид
    
    Args:
        detailed_dict: словарь с детальной статистикой
        category: категория ('killed', 'mined', 'killed_by')
        limit: количество записей для отображения
    
    Returns:
        Отформатированная строка
    """
    if not detailed_dict:
        return "Нет данных"
    
    # Сортируем по значению (убывание)
    sorted_items = sorted(detailed_dict.items(), key=lambda x: x[1], reverse=True)[:limit]
    
    lines = []
    for key, value in sorted_items:
        # Убираем префикс "minecraft:"
        name = key.replace('minecraft:', '')
        # Заменяем подчеркивания на пробелы
        name = name.replace('_', ' ').title()
        lines.append(f"  • <b>{name}:</b> {value}")
    
    return "\n".join(lines) if lines else "Нет данных"


def get_top_killed_mobs(killed_dict: dict, limit: int = 5) -> List[Tuple[str, int]]:
    """Возвращает топ убитых мобов"""
    if not killed_dict:
        return []
    sorted_items = sorted(killed_dict.items(), key=lambda x: x[1], reverse=True)[:limit]
    return [(k.replace('minecraft:', '').replace('_', ' ').title(), v) for k, v in sorted_items]


def get_top_mined_blocks(mined_dict: dict, limit: int = 5) -> List[Tuple[str, int]]:
    """Возвращает топ добытых блоков"""
    if not mined_dict:
        return []
    sorted_items = sorted(mined_dict.items(), key=lambda x: x[1], reverse=True)[:limit]
    return [(k.replace('minecraft:', '').replace('_', ' ').title(), v) for k, v in sorted_items]


def get_top_deaths_from(killed_by_dict: dict, limit: int = 5) -> List[Tuple[str, int]]:
    """Возвращает топ причин смерти"""
    if not killed_by_dict:
        return []
    sorted_items = sorted(killed_by_dict.items(), key=lambda x: x[1], reverse=True)[:limit]
    return [(k.replace('minecraft:', '').replace('_', ' ').title(), v) for k, v in sorted_items]
