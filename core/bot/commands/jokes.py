"""
Команды для получения анекдотов и цитат с rzhunemogu.ru
"""
import logging
import random
import json
import re
import aiohttp
from telegram import Update
from telegram.ext import Application, ContextTypes, CommandHandler

from .base import CommandBase, NOTIFICATION_GROUP_ID
from core.config import NOTIFICATION_TOPICS

logger = logging.getLogger(__name__)

# Константы для API
JOKE_API_URL = "http://rzhunemogu.ru/RandJSON.aspx"
JOKE_TYPES = {
    1: "Анекдот",
    2: "Рассказы",
    3: "Стишки",
    4: "Афоризмы",
    5: "Цитаты",
    6: "Тосты",
    8: "Статусы",
    11: "Анекдот (+18)",
    12: "Рассказы (+18)",
    13: "Стишки (+18)",
    14: "Афоризмы (+18)",
    15: "Цитаты (+18)",
    16: "Тосты (+18)",
    18: "Статусы (+18)",
}


class JokeCommands(CommandBase):
    """Команды для получения анекдотов"""
    
    def __init__(self, facade, admin_checker, keyboard_builder, user_registrar=None, group_registrar=None, minecraft_ssh_config=None):
        super().__init__(facade, admin_checker, keyboard_builder, user_registrar, group_registrar)
        self.minecraft_ssh_config = minecraft_ssh_config
    
    async def get_random_joke(self) -> tuple[str, str]:
        """
        Получает случайный анекдот/цитату с API
        
        Returns:
            tuple[str, str]: (тип контента, текст контента)
        """
        # Выбираем случайный тип контента
        content_type = random.choice(list(JOKE_TYPES.keys()))
        content_type_name = JOKE_TYPES[content_type]
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    JOKE_API_URL,
                    params={"CType": content_type},
                    timeout=aiohttp.ClientTimeout(total=10)
                ) as response:
                    if response.status != 200:
                        logger.error(f"API вернул статус {response.status}")
                        return None, "❌ Не удалось получить анекдот (ошибка API)"
                    
                    # Читаем ответ как текст, чтобы обработать control characters
                    text = await response.text()
                    
                    # Удаляем или заменяем недопустимые control characters (кроме \n, \r, \t)
                    # Оставляем только стандартные whitespace символы
                    cleaned_text = re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]', '', text)
                    
                    try:
                        # Парсим JSON
                        data = json.loads(cleaned_text)
                        content = data.get("content", "").strip()
                        
                        if not content:
                            logger.error("API вернул пустой контент")
                            return None, "❌ Не удалось получить анекдот (пустой ответ)"
                        
                        return content_type_name, content
                    except json.JSONDecodeError as e:
                        logger.error(f"Ошибка парсинга JSON: {e}, текст ответа: {text[:200]}")
                        # Попробуем извлечь content вручную, если JSON невалидный
                        match = re.search(r'"content"\s*:\s*"([^"]*(?:\\.[^"]*)*)"', cleaned_text)
                        if match:
                            content = match.group(1).replace('\\"', '"').replace('\\n', '\n').replace('\\r', '\r').strip()
                            if content:
                                return content_type_name, content
                        return None, "❌ Не удалось обработать ответ от API"
                    
        except aiohttp.ClientError as e:
            logger.error(f"Ошибка при запросе к API: {e}")
            return None, "❌ Не удалось получить анекдот (ошибка сети)"
        except Exception as e:
            logger.error(f"Неожиданная ошибка: {e}", exc_info=True)
            return None, "❌ Произошла ошибка при получении анекдота"
    
    async def _send_joke_to_minecraft(self, content_type: str, content: str):
        """
        Отправляет анекдот в Minecraft чат (тихо, без ошибок пользователю)
        
        Args:
            content_type: Тип контента (например, "Анекдот")
            content: Текст анекдота
        """
        if not self.minecraft_ssh_config:
            logger.debug("Minecraft SSH config не настроен, пропускаем отправку в MC")
            return
        
        try:
            # Проверяем, что сервер запущен
            from core.minecraft.service import is_ready
            server_ready = await is_ready(self.minecraft_ssh_config)
            
            if not server_ready:
                logger.debug("Minecraft сервер не запущен, пропускаем отправку анекдота")
                return
            
            # Формируем сообщение для Minecraft
            # Используем формат: [Telegram: Анекдот] текст анекдота
            minecraft_message = f"{content_type}: {content}"
            
            # Отправляем через RCON
            from core.minecraft.rcon import say
            success = await say(self.minecraft_ssh_config, minecraft_message, sender="Анекдот")
            
            if success:
                logger.info(f"✅ Анекдот отправлен в Minecraft: {content_type}")
            else:
                logger.debug(f"Не удалось отправить анекдот в Minecraft (RCON недоступен или ошибка)")
                
        except Exception as e:
            # Тихая обработка ошибок - не показываем пользователю
            logger.debug(f"Ошибка при отправке анекдота в Minecraft (тихо игнорируем): {e}")
    
    async def handle_joke_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """
        Обработчик callback для кнопки "Анекдот для Вовы"
        """
        query = update.callback_query
        user = update.effective_user
        chat = update.effective_chat
        
        # Register user and group
        self._register_user_if_needed(user)
        self._register_group_if_needed(chat)
        
        # Отвечаем на callback сразу, чтобы показать что обрабатываем
        await query.answer("🎲 Получаю анекдот...")
        
        # Получаем анекдот
        content_type, content = await self.get_random_joke()
        
        if content_type:
            # Формируем красивое сообщение
            message_text = f"😂 <b>{content_type}</b>\n\n{content}"
        else:
            # Если ошибка, content уже содержит текст ошибки
            message_text = content
        
        # Отправляем анекдот
        try:
            await query.message.reply_text(
                message_text,
                parse_mode="HTML"
            )
            logger.info(f"Анекдот отправлен пользователю {user.id} ({user.username or user.first_name})")
            
            # Отправляем анекдот в Minecraft (тихо, без ошибок пользователю)
            if content_type:
                await self._send_joke_to_minecraft(content_type, content)
        except Exception as e:
            logger.error(f"Ошибка при отправке анекдота: {e}")
            await query.message.reply_text("❌ Ошибка при отправке анекдота")
    
    async def handle_joke_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """
        Обработчик команды /joke
        Отправляет анекдот в тред группы или отвечает в личке
        """
        user = update.effective_user
        chat = update.effective_chat
        
        # Register user and group
        self._register_user_if_needed(user)
        self._register_group_if_needed(chat)
        
        # Получаем анекдот
        content_type, content = await self.get_random_joke()
        
        if content_type:
            message_text = f"😂 <b>{content_type}</b>\n\n{content}"
        else:
            # Если ошибка, content уже содержит текст ошибки
            message_text = content
        
        # Отправляем анекдот
        try:
            if chat.id == NOTIFICATION_GROUP_ID:
                # Отправляем в тред группы jokes
                # Используем update.get_bot() для получения бота
                bot = update.get_bot()
                logger.debug(f"Отправка анекдота в группу {NOTIFICATION_GROUP_ID}, тред {NOTIFICATION_TOPICS['jokes']}")
                await bot.send_message(
                    chat_id=NOTIFICATION_GROUP_ID,
                    text=message_text,
                    parse_mode="HTML",
                    message_thread_id=NOTIFICATION_TOPICS['jokes']
                )
            else:
                # Отвечаем в личке или другой группе
                await update.message.reply_text(
                    message_text,
                    parse_mode="HTML"
                )
            logger.info(f"Анекдот отправлен через /joke пользователю {user.id} ({user.username or user.first_name})")
            
            # Отправляем анекдот в Minecraft (тихо, без ошибок пользователю)
            if content_type:
                await self._send_joke_to_minecraft(content_type, content)
        except Exception as e:
            logger.error(f"Ошибка при отправке анекдота: {e}", exc_info=True)
            try:
                await update.message.reply_text("❌ Ошибка при отправке анекдота")
            except Exception as e2:
                logger.error(f"Не удалось отправить сообщение об ошибке: {e2}")


def register_joke_handlers(app: Application, facade, is_admin_checker, keyboard_builder, user_registrar=None, group_registrar=None, minecraft_ssh_config=None):
    """
    Регистрирует обработчики команд анекдотов
    
    Args:
        app: Telegram Application
        facade: ServerFacade
        is_admin_checker: Функция проверки прав администратора
        keyboard_builder: Функция построения клавиатуры
        user_registrar: Функция регистрации пользователя
        group_registrar: Функция регистрации группы
        minecraft_ssh_config: Конфигурация SSH для Minecraft сервера
    
    Note: Callback handler регистрируется в bot.py в функции button_callback
    """
    commands = JokeCommands(facade, is_admin_checker, keyboard_builder, user_registrar, group_registrar, minecraft_ssh_config)
    
    # Регистрируем обработчик команды /joke
    app.add_handler(CommandHandler("joke", commands.handle_joke_command))
    
    logger.info("✅ Команды анекдотов зарегистрированы")
    
    # Возвращаем объект команд для использования в button_callback
    return commands
