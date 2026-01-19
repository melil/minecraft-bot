"""
Базовые классы и утилиты для команд
"""
import logging
from telegram import Update
from telegram.ext import ContextTypes

logger = logging.getLogger(__name__)

# Hardcoded supergroup ID (supergroup с топиками)
NOTIFICATION_GROUP_ID = -1003506839886


class CommandBase:
    """Базовый класс для команд"""
    
    def __init__(self, facade, admin_checker, keyboard_builder, user_registrar=None, group_registrar=None):
        self.facade = facade
        self.is_admin = admin_checker
        self.get_keyboard = keyboard_builder
        self.register_user = user_registrar
        self.register_group = group_registrar
        
    def _register_user_if_needed(self, user):
        """Register user if registrar is provided"""
        if self.register_user and user:
            self.register_user(user)
    
    def _register_group_if_needed(self, chat):
        """Register group if registrar is provided"""
        if self.register_group and chat and chat.type in ["group", "supergroup"]:
            self.register_group(chat)
    
    def _is_allowed_group(self, chat_id: int) -> bool:
        """Check if this is the allowed group"""
        return chat_id == NOTIFICATION_GROUP_ID
        
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
