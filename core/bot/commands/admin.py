"""
Административные команды: add_admin, del_admin, list_admins, set_minecraft_nick, promote_super_admin
"""
import logging
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes

from core.database import UserRole
from .base import CommandBase

logger = logging.getLogger(__name__)


class AdminCommands(CommandBase):
    """Административные команды"""
    
    def __init__(self, facade, admin_checker, keyboard_builder, admin_manager, user_registrar=None, group_registrar=None):
        super().__init__(facade, admin_checker, keyboard_builder, user_registrar, group_registrar)
        self.admin_manager = admin_manager
    
    async def add_admin_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Добавляет администратора"""
        chat = update.effective_chat
        user = update.effective_user
        
        # Register user
        self._register_user_if_needed(user)

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
        
        # Register user
        self._register_user_if_needed(user)

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
        
        # Register user
        self._register_user_if_needed(user)

        if chat.type != "private":
            return

        if not self.is_admin(user.id):
            await update.message.reply_text("❌ У вас нет прав для выполнения этой команды.")
            return

        admins = self.admin_manager.get_admins()
        if admins:
            admins_list = "\n".join(f"• {admin}" for admin in admins)
            await update.message.reply_text(f"👑 Администраторы ({len(admins)}):\n{admins_list}")
        else:
            await update.message.reply_text("📭 Список администраторов пуст.")
    
    async def set_minecraft_nick_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Устанавливает Minecraft ник пользователю"""
        chat = update.effective_chat
        user = update.effective_user
        
        # Register user
        self._register_user_if_needed(user)
        
        if chat.type != "private":
            return
        
        # Usage: /set_minecraft_nick <user_id> <nickname>
        # Or: /set_minecraft_nick <nickname> (for self)
        if not context.args:
            await update.message.reply_text(
                "Использование:\n"
                "/set_minecraft_nick <никнейм> - установить свой ник\n"
                "/set_minecraft_nick <user_id> <никнейм> - установить ник другому пользователю (только для админов)"
            )
            return
        
        # If one argument, set for self
        if len(context.args) == 1:
            nickname = context.args[0]
            if self.admin_manager.set_minecraft_nickname(user.id, nickname):
                await update.message.reply_text(f"✅ Ваш Minecraft ник установлен: {nickname}")
            else:
                await update.message.reply_text("❌ Ошибка при установке никнейма")
            return
        
        # If two arguments, admin can set for another user
        if len(context.args) == 2:
            if not self.is_admin(user.id):
                await update.message.reply_text("❌ У вас нет прав для установки ника другим пользователям.")
                return
            
            try:
                target_user_id = int(context.args[0])
                nickname = context.args[1]
                
                if self.admin_manager.set_minecraft_nickname(target_user_id, nickname):
                    await update.message.reply_text(f"✅ Minecraft ник пользователя {target_user_id} установлен: {nickname}")
                else:
                    await update.message.reply_text(f"❌ Пользователь {target_user_id} не найден")
            except ValueError:
                await update.message.reply_text("❌ Неверный ID пользователя")
            return
    
    async def promote_super_admin_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Повышает пользователя до супер-админа (только для супер-админов)"""
        chat = update.effective_chat
        user = update.effective_user
        
        # Register user
        self._register_user_if_needed(user)
        
        if chat.type != "private":
            return
        
        # Check if user is super admin
        if not self.admin_manager.is_super_admin(user.id):
            await update.message.reply_text("❌ Только супер-админы могут выполнять эту команду.")
            return
        
        if not context.args:
            await update.message.reply_text("Использование: /promote_super_admin <user_id>")
            return
        
        try:
            target_user_id = int(context.args[0])
            if self.admin_manager.promote_super_admin(target_user_id):
                await update.message.reply_text(f"✅ Пользователь {target_user_id} повышен до супер-администратора.")
            else:
                await update.message.reply_text(f"❌ Не удалось повысить пользователя {target_user_id}")
        except ValueError:
            await update.message.reply_text("❌ Неверный ID пользователя.")


def register_admin_handlers(app: Application, facade, is_admin_checker, keyboard_builder, admin_manager, user_registrar=None, group_registrar=None):
    """Регистрирует административные команды"""
    commands = AdminCommands(facade, is_admin_checker, keyboard_builder, admin_manager, user_registrar, group_registrar)
    
    app.add_handler(CommandHandler("add_admin", commands.add_admin_command))
    app.add_handler(CommandHandler("del_admin", commands.del_admin_command))
    app.add_handler(CommandHandler("list_admins", commands.list_admins_command))
    app.add_handler(CommandHandler("set_minecraft_nick", commands.set_minecraft_nick_command))
    app.add_handler(CommandHandler("promote_super_admin", commands.promote_super_admin_command))
    
    logger.info("✅ Административные команды зарегистрированы")
