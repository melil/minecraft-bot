"""
Система мониторинга логов Minecraft сервера
Отслеживает события: вход/выход игроков, сообщения в чате, смерти, достижения
"""
import asyncio
import logging
import re
from datetime import datetime
from typing import Optional, Callable, Dict, Any
from dataclasses import dataclass
from core.ssh.client import SSHClient

logger = logging.getLogger(__name__)


@dataclass
class MinecraftEvent:
    """Базовый класс для события Minecraft"""
    event_type: str  # 'join', 'leave', 'chat', 'death', 'achievement'
    timestamp: datetime
    raw_message: str
    
    def format_telegram(self) -> str:
        """Форматирует событие для отправки в Telegram"""
        raise NotImplementedError


@dataclass
class PlayerJoinEvent(MinecraftEvent):
    """Событие входа игрока"""
    player_name: str
    
    def format_telegram(self) -> str:
        return f"➕ <b>{self.player_name}</b> присоединился к игре"


@dataclass
class PlayerLeaveEvent(MinecraftEvent):
    """Событие выхода игрока"""
    player_name: str
    
    def format_telegram(self) -> str:
        return f"➖ <b>{self.player_name}</b> покинул игру"


@dataclass
class ChatMessageEvent(MinecraftEvent):
    """Событие сообщения в чате"""
    player_name: str
    message: str
    
    def format_telegram(self) -> str:
        return f"💬 <b>{self.player_name}:</b> {self.message}"


@dataclass
class TelegramMessageEvent(MinecraftEvent):
    """Событие сообщения для Telegram (префикс tg)"""
    player_name: str
    message: str
    
    def format_telegram(self) -> str:
        return f"📨 <b>{self.player_name}:</b> {self.message}"


@dataclass
class PlayerDeathEvent(MinecraftEvent):
    """Событие смерти игрока"""
    death_message: str
    player_name: Optional[str] = None
    
    def format_telegram(self) -> str:
        return f"💀 {self.death_message}"


@dataclass
class PlayerAchievementEvent(MinecraftEvent):
    """Событие получения достижения"""
    player_name: str
    achievement: str
    
    def format_telegram(self) -> str:
        return f"🏆 <b>{self.player_name}</b> получил достижение: <i>{self.achievement}</i>"


class MinecraftLogParser:
    """Парсер логов Minecraft"""
    
    # Паттерны для разных типов событий
    PATTERNS = {
        # [12:34:56] [Server thread/INFO]: Player joined the game
        'join': re.compile(r':\s*(\w+)\s+joined the game', re.IGNORECASE),
        
        # [12:34:56] [Server thread/INFO]: Player left the game
        'leave': re.compile(r':\s*(\w+)\s+left the game', re.IGNORECASE),
        
        # [12:34:56] [Server thread/INFO]: <Player> Hello world
        'chat': re.compile(r':\s*<(\w+)>\s*(.+)$', re.IGNORECASE),
        
        # [12:34:56] [Server thread/INFO]: Player was slain by Zombie
        # Различные варианты сообщений о смерти
        'death': re.compile(
            r':\s*(\w+)\s+(was|drowned|experienced|blew|hit|fell|went|walked|discovered|'
            r'burned|tried|suffocated|starved|died|withered|froze|didn\'t)',
            re.IGNORECASE
        ),
        
        # [12:34:56] [Server thread/INFO]: Player has made the advancement [Stone Age]
        # [12:34:56] [Server thread/INFO]: Player has completed the challenge [Monster Hunter]
        'achievement': re.compile(
            r':\s*(\w+)\s+has\s+(made\s+the\s+advancement|completed\s+the\s+challenge|reached\s+the\s+goal)\s+\[(.+?)\]',
            re.IGNORECASE
        ),
        
        # [12:34:56] [Server thread/INFO]: [Not Secure] <Player> telegram: message text
        # Важно: проверяем префикс telegram: в начале сообщения
        'telegram_message': re.compile(
            r':\s*(?:\[Not Secure\]\s*)?<(\w+)>\s*telegram:\s*(.+)$',
            re.IGNORECASE
        ),
    }
    
    @staticmethod
    def parse_line(line: str) -> Optional[MinecraftEvent]:
        """
        Парсит строку лога и возвращает событие, если найдено
        """
        try:
            # Извлекаем timestamp из строки (если есть)
            timestamp = datetime.now()
            
            # Проверяем каждый тип события
            
            # 1. Вход игрока
            match = MinecraftLogParser.PATTERNS['join'].search(line)
            if match:
                player_name = match.group(1)
                return PlayerJoinEvent(
                    event_type='join',
                    timestamp=timestamp,
                    raw_message=line,
                    player_name=player_name
                )
            
            # 2. Выход игрока
            match = MinecraftLogParser.PATTERNS['leave'].search(line)
            if match:
                player_name = match.group(1)
                return PlayerLeaveEvent(
                    event_type='leave',
                    timestamp=timestamp,
                    raw_message=line,
                    player_name=player_name
                )
            
            # 3. Сообщения для Telegram (с префиксом "telegram:")
            # ВАЖНО: проверяем ДО обычных chat-сообщений!
            match = MinecraftLogParser.PATTERNS['telegram_message'].search(line)
            if match:
                player_name = match.group(1)
                message = match.group(2).strip()
                return TelegramMessageEvent(
                    event_type='telegram_message',
                    timestamp=timestamp,
                    raw_message=line,
                    player_name=player_name,
                    message=message
                )
            
            # 4. Сообщение в чате
            match = MinecraftLogParser.PATTERNS['chat'].search(line)
            if match:
                player_name = match.group(1)
                message = match.group(2).strip()
                
                # Игнорируем сообщения от бота (Telegram)
                if '[Telegram' in message or message.startswith('[Telegram'):
                    return None
                
                # Обычное сообщение в чате
                return ChatMessageEvent(
                    event_type='chat',
                    timestamp=timestamp,
                    raw_message=line,
                    player_name=player_name,
                    message=message
                )
            
            # 5. Достижения
            match = MinecraftLogParser.PATTERNS['achievement'].search(line)
            if match:
                player_name = match.group(1)
                achievement = match.group(3)
                return PlayerAchievementEvent(
                    event_type='achievement',
                    timestamp=timestamp,
                    raw_message=line,
                    player_name=player_name,
                    achievement=achievement
                )
            
            # 6. Смерть (должна быть последней, т.к. паттерн широкий)
            match = MinecraftLogParser.PATTERNS['death'].search(line)
            if match:
                # Извлекаем полное сообщение о смерти
                # Ищем текст после последнего ":"
                parts = line.split(':')
                if len(parts) >= 2:
                    death_message = parts[-1].strip()
                    player_name = match.group(1)
                    return PlayerDeathEvent(
                        event_type='death',
                        timestamp=timestamp,
                        raw_message=line,
                        death_message=death_message,
                        player_name=player_name
                    )
            
            return None
            
        except Exception as e:
            logger.error(f"Ошибка парсинга строки лога: {e}, строка: {line[:100]}")
            return None


class MinecraftLogMonitor:
    """
    Мониторинг логов Minecraft в реальном времени
    """
    
    def __init__(
        self,
        ssh_config: dict,
        event_callback: Callable[[MinecraftEvent], None],
        check_interval: int = 2
    ):
        """
        Args:
            ssh_config: Конфигурация SSH для подключения к серверу
            event_callback: Async функция-обработчик событий
            check_interval: Интервал проверки логов в секундах
        """
        self.ssh_config = ssh_config
        self.event_callback = event_callback
        self.check_interval = check_interval
        self.is_running = False
        self.task = None
        self.parser = MinecraftLogParser()
        self.last_log_line = None  # Для отслеживания последней обработанной строки
    
    async def start(self):
        """Запускает мониторинг логов"""
        if self.is_running:
            logger.warning("Мониторинг логов уже запущен")
            return
        
        self.is_running = True
        self.task = asyncio.create_task(self._monitor_loop())
        logger.info("🔍 Мониторинг логов Minecraft запущен")
    
    async def stop(self):
        """Останавливает мониторинг логов"""
        if not self.is_running:
            return
        
        self.is_running = False
        if self.task:
            self.task.cancel()
            try:
                await self.task
            except asyncio.CancelledError:
                pass
        
        logger.info("🛑 Мониторинг логов Minecraft остановлен")
    
    async def _monitor_loop(self):
        """Основной цикл мониторинга"""
        logger.info(f"🔄 Мониторинг логов: цикл запущен (интервал: {self.check_interval}с)")
        try:
            iteration = 0
            while self.is_running:
                try:
                    iteration += 1
                    logger.debug(f"📝 Мониторинг логов: итерация {iteration}")
                    await self._check_logs()
                except Exception as e:
                    logger.error(f"❌ Ошибка в цикле мониторинга логов: {e}", exc_info=True)
                
                await asyncio.sleep(self.check_interval)
        
        except asyncio.CancelledError:
            logger.info("🛑 Мониторинг логов: цикл отменён")
    
    async def _check_logs(self):
        """Проверяет новые записи в логах"""
        try:
            client = SSHClient(**self.ssh_config)
            
            # Получаем последние 50 строк логов
            # Используем --output=cat чтобы получить полные строки без обрезания
            command = f"journalctl -u minecraft.service --since '{self.check_interval + 5} seconds ago' --no-pager --output=cat -n 50 2>/dev/null || echo ''"
            logger.debug(f"📜 Выполнение: {command}")
            
            result = await client.execute(command, timeout=10)
            
            logger.debug(f"📋 Получено логов: {len(result)} символов")
            
            if not result or result.strip() == '':
                logger.debug("⏭️ Логи пусты, пропуск")
                return
            
            lines = result.strip().split('\n')
            logger.debug(f"📄 Обработка {len(lines)} строк логов")
            
            # Обрабатываем каждую строку
            new_events = 0
            for i, line in enumerate(lines):
                # Пропускаем пустые строки
                if not line.strip():
                    continue
                
                logger.debug(f"📃 Строка {i+1}: {line[:150]}")  # Первые 150 символов
                
                # Пропускаем уже обработанные строки
                if self.last_log_line and line == self.last_log_line:
                    logger.debug(f"⏭️ Строка уже обработана, пропуск")
                    continue
                
                # Парсим событие
                event = self.parser.parse_line(line)
                
                if event:
                    new_events += 1
                    logger.info(f"🎯 Найдено событие: {event.event_type} ({event.player_name if hasattr(event, 'player_name') else 'N/A'})")
                    # Вызываем callback для обработки события
                    try:
                        await self.event_callback(event)
                        logger.info(f"✅ Событие обработано: {event.event_type}")
                    except Exception as e:
                        logger.error(f"❌ Ошибка в callback обработчике события: {e}", exc_info=True)
            
            if new_events > 0:
                logger.info(f"📊 Обработано новых событий: {new_events}")
            
            # Сохраняем последнюю строку
            if lines:
                self.last_log_line = lines[-1]
        
        except Exception as e:
            logger.error(f"❌ Ошибка проверки логов: {e}", exc_info=True)


# ==================== УТИЛИТЫ ====================

def format_event_for_telegram(event: MinecraftEvent) -> str:
    """
    Форматирует событие Minecraft для отправки в Telegram
    """
    return event.format_telegram()


async def send_event_to_telegram(
    event: MinecraftEvent,
    bot_application,
    chat_id: int,
    enabled_events: Optional[Dict[str, bool]] = None
):
    """
    Отправляет событие в Telegram чат
    
    Args:
        event: Событие Minecraft
        bot_application: Telegram bot application
        chat_id: ID чата для отправки
        enabled_events: Словарь с включенными типами событий
    """
    # Проверяем, включен ли данный тип события
    if enabled_events and not enabled_events.get(event.event_type, True):
        return
    
    try:
        message = format_event_for_telegram(event)
        
        await bot_application.bot.send_message(
            chat_id=chat_id,
            text=message,
            parse_mode="HTML"
        )
        
        logger.info(f"📤 Событие отправлено в Telegram: {event.event_type}")
        
    except Exception as e:
        logger.error(f"Ошибка отправки события в Telegram: {e}")
