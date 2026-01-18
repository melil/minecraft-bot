"""
Команды настроек: settings, toggle auto shutdown
"""
import logging
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes

from .base import CommandBase

logger = logging.getLogger(__name__)


class SettingsCommands(CommandBase):
    """Команды настроек"""
    
    def __init__(self, facade, admin_checker, keyboard_builder, settings_manager, idle_timeout, user_registrar=None, group_registrar=None):
        super().__init__(facade, admin_checker, keyboard_builder, user_registrar, group_registrar)
        self.settings_manager = settings_manager
        self.idle_timeout = idle_timeout
    
    async def settings_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработчик команды /settings"""
        user = update.effective_user
        chat = update.effective_chat
        
        # Register user and group
        self._register_user_if_needed(user)
        self._register_group_if_needed(chat)
        
        # Allow in group or private chat for admins
        if chat.type in ["group", "supergroup"]:
            if not self._is_allowed_group(chat.id):
                return
        elif chat.type == "private":
            if not self.is_admin(user.id):
                await update.message.reply_text("❌ У вас нет прав для выполнения этой команды.")
                return
        else:
            return

        auto_status = "🟢 Включено" if self.settings_manager.is_auto_shutdown_enabled() else "🔴 Отключено"
        settings_text = (
            "⚙️ <b>Настройки сервера</b>\n\n"
            f"⏱️ <b>Автовыключение:</b> {auto_status}\n"
            f"<i>Сервер выключается через {self.idle_timeout // 60} мин. при 0 игроков</i>\n\n"
            "Используйте кнопки ниже для изменения настроек:"
        )
        
        keyboard = self.settings_manager.get_settings_keyboard()
        await update.message.reply_text(
            settings_text,
            reply_markup=keyboard,
            parse_mode="HTML"
        )


def register_settings_handlers(app: Application, facade, is_admin_checker, keyboard_builder, settings_manager, idle_timeout, user_registrar=None, group_registrar=None):
    """Регистрирует команды настроек"""
    commands = SettingsCommands(facade, is_admin_checker, keyboard_builder, settings_manager, idle_timeout, user_registrar, group_registrar)
    
    app.add_handler(CommandHandler("settings", commands.settings_command))
    
    logger.info("✅ Команды настроек зарегистрированы")
