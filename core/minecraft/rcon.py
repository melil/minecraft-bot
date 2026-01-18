"""
RCON клиент для отправки команд в Minecraft сервер
"""
import logging
from typing import Optional
from core.ssh.client import SSHClient
from core.config import MINECRAFT_RCON_PASSWORD

logger = logging.getLogger(__name__)

# RCON настройки
RCON_HOST = "127.0.0.1"
RCON_PORT = 25575


async def execute_rcon_command(ssh_config: dict, command: str) -> Optional[str]:
    """
    Выполняет RCON команду на Minecraft сервере
    
    Args:
        ssh_config: Конфигурация SSH подключения
        command: Команда для выполнения (например: "say Hello World")
        
    Returns:
        Ответ от сервера или None при ошибке
    """
    try:
        client = SSHClient(**ssh_config)
        
        # Экранируем кавычки и специальные символы в команде
        escaped_command = command.replace("'", "'\\''")
        
        # Выполняем RCON команду через mcrcon
        result = await client.execute(
            f"mcrcon -H {RCON_HOST} -P {RCON_PORT} -p '{MINECRAFT_RCON_PASSWORD}' '{escaped_command}' 2>&1",
            timeout=10
        )
        
        logger.debug(f"RCON команда '{command}' выполнена: {result[:200]}")
        return result.strip()
        
    except Exception as e:
        logger.error(f"Ошибка выполнения RCON команды '{command}': {e}")
        return None


async def say(ssh_config: dict, message: str, sender: Optional[str] = None) -> bool:
    """
    Отправляет сообщение в игровой чат через команду /say
    
    Args:
        ssh_config: Конфигурация SSH подключения
        message: Текст сообщения
        sender: Имя отправителя (будет добавлено в формате [Telegram: имя])
        
    Returns:
        True если успешно, False если ошибка
    """
    try:
        # Формируем сообщение с отправителем
        if sender:
            full_message = f"[Telegram: {sender}] {message}"
        else:
            full_message = f"[Telegram] {message}"
        
        # Отправляем через say команду
        result = await execute_rcon_command(ssh_config, f"say {full_message}")
        
        if result is not None:
            logger.info(f"✅ Сообщение отправлено в Minecraft: {full_message}")
            return True
        else:
            logger.error(f"❌ Не удалось отправить сообщение в Minecraft")
            return False
            
    except Exception as e:
        logger.error(f"Ошибка отправки сообщения: {e}")
        return False


async def tellraw(ssh_config: dict, message: str, color: str = "white", sender: Optional[str] = None) -> bool:
    """
    Отправляет форматированное сообщение в чат через tellraw
    
    Args:
        ssh_config: Конфигурация SSH подключения
        message: Текст сообщения
        color: Цвет текста (white, yellow, aqua, green, red, etc.)
        sender: Имя отправителя
        
    Returns:
        True если успешно, False если ошибка
    """
    try:
        # Экранируем кавычки в сообщении
        escaped_message = message.replace('"', '\\"')
        
        # Формируем JSON для tellraw
        if sender:
            json_message = (
                f'{{"text":"[Telegram: {sender}] ","color":"aqua"}},'
                f'{{"text":"{escaped_message}","color":"{color}"}}'
            )
        else:
            json_message = (
                f'{{"text":"[Telegram] ","color":"aqua"}},'
                f'{{"text":"{escaped_message}","color":"{color}"}}'
            )
        
        # Отправляем команду tellraw @a (всем игрокам)
        result = await execute_rcon_command(ssh_config, f"tellraw @a [{json_message}]")
        
        if result is not None:
            logger.info(f"✅ Форматированное сообщение отправлено в Minecraft")
            return True
        else:
            logger.error(f"❌ Не удалось отправить форматированное сообщение")
            return False
            
    except Exception as e:
        logger.error(f"Ошибка отправки форматированного сообщения: {e}")
        return False


async def list_players(ssh_config: dict) -> Optional[list]:
    """
    Получает список игроков через RCON команду /list
    
    Returns:
        Список имен игроков или None при ошибке
    """
    try:
        result = await execute_rcon_command(ssh_config, "list")
        
        if result and "There are" in result:
            # Парсим ответ: "There are 2 of a max of 20 players online: Player1, Player2"
            if ":" in result and "online" in result.lower():
                parts = result.split(":")
                if len(parts) > 1:
                    names_str = parts[1].strip()
                    # Убираем ANSI escape коды
                    import re
                    names_clean = re.sub(r'\x1b\[[0-9;]*m', '', names_str)
                    names = [n.strip() for n in names_clean.split(',') if n.strip()]
                    return names
        
        return []
        
    except Exception as e:
        logger.error(f"Ошибка получения списка игроков: {e}")
        return None
