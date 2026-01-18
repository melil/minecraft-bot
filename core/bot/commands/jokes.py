"""
Команды для получения анекдотов и цитат с rzhunemogu.ru
"""
import logging
import random
import aiohttp
from telegram import Update
from telegram.ext import Application, ContextTypes

from .base import CommandBase

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
    
    def __init__(self, facade, admin_checker, keyboard_builder, user_registrar=None, group_registrar=None):
        super().__init__(facade, admin_checker, keyboard_builder, user_registrar, group_registrar)
    
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
                    
                    data = await response.json()
                    content = data.get("content", "").strip()
                    
                    if not content:
                        logger.error("API вернул пустой контент")
                        return None, "❌ Не удалось получить анекдот (пустой ответ)"
                    
                    return content_type_name, content
                    
        except aiohttp.ClientError as e:
            logger.error(f"Ошибка при запросе к API: {e}")
            return None, "❌ Не удалось получить анекдот (ошибка сети)"
        except Exception as e:
            logger.error(f"Неожиданная ошибка: {e}")
            print(f"Неожиданная ошибка: {e}")
            return None, "❌ Произошла ошибка при получении анекдота"
    
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
        except Exception as e:
            logger.error(f"Ошибка при отправке анекдота: {e}")
            await query.message.reply_text("❌ Ошибка при отправке анекдота")


def register_joke_handlers(app: Application, facade, is_admin_checker, keyboard_builder, user_registrar=None, group_registrar=None):
    """
    Регистрирует обработчики команд анекдотов
    
    Note: Callback handler регистрируется в bot.py в функции button_callback
    """
    commands = JokeCommands(facade, is_admin_checker, keyboard_builder, user_registrar, group_registrar)
    
    logger.info("✅ Команды анекдотов зарегистрированы")
    
    # Возвращаем объект команд для использования в button_callback
    return commands
