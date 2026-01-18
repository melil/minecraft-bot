"""
Административные команды: add_admin, del_admin, list_admins
"""
import logging
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes

from .base import CommandBase

logger = logging.getLogger(__name__)


class AdminCommands(CommandBase):
    """Административные команды"""
    
    def __init__(self, facade, admin_checker, keyboard_builder, admin_manager):
        super().__init__(facade, admin_checker, keyboard_builder)
        self.admin_manager = admin_manager
    
    async def add_admin_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Добавляет администратора"""
        chat = update.effective_chat
        user = update.effective_user

        if chat.type != "private":
            return

        if not self.is_admin(user.id):
            await update.message.reply_text("❌ У вас нет прав для выполнения этой команды.")
            return

        if not context.args:
            await update.message.reply_text("Использование: /add_admin <user_id>")
            return

        try:
            new_admin_id = int(context.args[0])
            self.admin_manager.add_admin(new_admin_id)
            await update.message.reply_text(f"✅ Пользователь {new_admin_id} добавлен в администраторы.")
        except ValueError:
            await update.message.reply_text("❌ Неверный ID пользователя.")

    async def del_admin_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Удаляет администратора"""
        chat = update.effective_chat
        user = update.effective_user

        if chat.type != "private":
            return

        if not self.is_admin(user.id):
            await update.message.reply_text("❌ У вас нет прав для выполнения этой команды.")
            return

        if not context.args:
            await update.message.reply_text("Использование: /del_admin <user_id>")
            return

        try:
            del_admin_id = int(context.args[0])
            if del_admin_id == user.id:
                await update.message.reply_text("❌ Нельзя удалить самого себя.")
                return

            if self.admin_manager.remove_admin(del_admin_id):
                await update.message.reply_text(f"✅ Пользователь {del_admin_id} удален из администраторов.")
            else:
                await update.message.reply_text(f"❌ Пользователь {del_admin_id} не найден в списке администраторов.")
        except ValueError:
            await update.message.reply_text("❌ Неверный ID пользователя.")

    async def list_admins_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Показывает список администраторов"""
        chat = update.effective_chat
        user = update.effective_user

        if chat.type != "private":
            return

        if not self.is_admin(user.id):
            await update.message.reply_text("❌ У вас нет прав для выполнения этой команды.")
            return

        admins = self.admin_manager.get_admins()
        if admins:
            admins_list = "\n".join(f"• {admin_id}" for admin_id in admins)
            await update.message.reply_text(f"👑 Администраторы ({len(admins)}):\n{admins_list}")
        else:
            await update.message.reply_text("📭 Список администраторов пуст.")


def register_admin_handlers(app: Application, facade, is_admin_checker, keyboard_builder, admin_manager):
    """Регистрирует административные команды"""
    commands = AdminCommands(facade, is_admin_checker, keyboard_builder, admin_manager)
    
    app.add_handler(CommandHandler("add_admin", commands.add_admin_command))
    app.add_handler(CommandHandler("del_admin", commands.del_admin_command))
    app.add_handler(CommandHandler("list_admins", commands.list_admins_command))
    
    logger.info("✅ Административные команды зарегистрированы")
