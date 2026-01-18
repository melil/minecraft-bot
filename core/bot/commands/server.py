"""
Команды управления сервером: start, stop, restart
"""
import logging
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes

from .base import CommandBase

logger = logging.getLogger(__name__)


class ServerCommands(CommandBase):
    """Команды управления сервером"""
    
    def __init__(self, facade, admin_checker, keyboard_builder, operation_manager):
        super().__init__(facade, admin_checker, keyboard_builder)
        self.operation_manager = operation_manager
    
    async def start_server_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработчик команды /start_server (только для админов в ЛС)"""
        chat = update.effective_chat
        user = update.effective_user

        if not self.is_admin(user.id):
            await update.message.reply_text("❌ У вас нет прав для выполнения этой команды.")
            return

        # Проверяем активные операции
        if self.operation_manager.is_active(chat.id):
            await update.message.reply_text("⚠️ Уже выполняется другая операция. Дождитесь завершения.")
            return

        logger.info(f"Пользователь {user.id} запустил команду /start_server")

        keyboard = await self.get_keyboard(True)
        msg = await update.message.reply_text(
            "▶️ Запускаю сервер в облаке...",
            reply_markup=keyboard
        )

        # Запускаем операцию через менеджер
        await self.operation_manager.start_operation("start", chat.id, msg.message_id, True)

    async def stop_server_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработчик команды /stop_server (только для админов в ЛС)"""
        chat = update.effective_chat
        user = update.effective_user

        if not self.is_admin(user.id):
            await update.message.reply_text("❌ У вас нет прав для выполнения этой команды.")
            return

        # Проверяем активные операции
        if self.operation_manager.is_active(chat.id):
            await update.message.reply_text("⚠️ Уже выполняется другая операция. Дождитесь завершения.")
            return

        keyboard = await self.get_keyboard(True)
        msg = await update.message.reply_text(
            "⏹️ Останавливаю сервер...",
            reply_markup=keyboard
        )

        # Запускаем операцию через менеджер
        await self.operation_manager.start_operation("stop", chat.id, msg.message_id, True)

    async def restart_server_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработчик команды /restart_server (только для админов в ЛС)"""
        chat = update.effective_chat
        user = update.effective_user

        if not self.is_admin(user.id):
            await update.message.reply_text("❌ У вас нет прав для выполнения этой команды.")
            return

        # Проверяем активные операции
        if self.operation_manager.is_active(chat.id):
            await update.message.reply_text("⚠️ Уже выполняется другая операция. Дождитесь завершения.")
            return

        keyboard = await self.get_keyboard(True)
        msg = await update.message.reply_text(
            "🔄 Перезагружаю сервер...",
            reply_markup=keyboard
        )

        # Запускаем операцию через менеджер
        await self.operation_manager.start_operation("restart", chat.id, msg.message_id, True)


def register_server_handlers(app: Application, facade, is_admin_checker, keyboard_builder, operation_manager):
    """Регистрирует команды управления сервером"""
    commands = ServerCommands(facade, is_admin_checker, keyboard_builder, operation_manager)
    
    app.add_handler(CommandHandler("start_server", commands.start_server_command))
    app.add_handler(CommandHandler("stop_server", commands.stop_server_command))
    app.add_handler(CommandHandler("restart_server", commands.restart_server_command))
    
    logger.info("✅ Команды управления сервером зарегистрированы")
