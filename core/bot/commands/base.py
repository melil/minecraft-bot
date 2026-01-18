"""
Базовые классы и утилиты для команд
"""
import logging
from telegram import Update
from telegram.ext import ContextTypes

logger = logging.getLogger(__name__)


class CommandBase:
    """Базовый класс для команд"""
    
    def __init__(self, facade, admin_checker, keyboard_builder):
        self.facade = facade
        self.is_admin = admin_checker
        self.get_keyboard = keyboard_builder
        
    async def check_admin(self, update: Update) -> bool:
        """Проверка прав администратора"""
        user = update.effective_user
        if not self.is_admin(user.id):
            await update.message.reply_text("❌ У вас нет прав для выполнения этой команды.")
            return False
        return True
    
    async def check_private_chat(self, update: Update) -> bool:
        """Проверка, что команда в личных сообщениях"""
        chat = update.effective_chat
        if chat.type != "private":
            await update.message.reply_text("⚠️ Эта команда доступна только в личных сообщениях.")
            return False
        return True
