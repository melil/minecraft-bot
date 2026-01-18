"""
Базовые классы и утилиты для команд
"""
import logging
from telegram import Update
from telegram.ext import ContextTypes

logger = logging.getLogger(__name__)


class CommandBase:
    """Базовый класс для команд"""
    
    def __init__(self, facade, admin_checker, keyboard_builder, user_registrar=None):
        self.facade = facade
        self.is_admin = admin_checker
        self.get_keyboard = keyboard_builder
        self.register_user = user_registrar
        
    def _register_user_if_needed(self, user):
        """Register user if registrar is provided"""
        if self.register_user and user:
            self.register_user(user)
        
    async def check_admin(self, update: Update) -> bool:
        """Проверка прав администратора"""
        user = update.effective_user
        self._register_user_if_needed(user)
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
