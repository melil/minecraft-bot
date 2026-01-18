"""
Информационные команды: start, help, status, players, ping
"""
import logging
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes

from core.domain.model.server_status import ServerStatus
from core.domain.model.server_state import ServerState
from .base import CommandBase

logger = logging.getLogger(__name__)


class InfoCommands(CommandBase):
    """Информационные команды"""
    
    def __init__(self, facade, admin_checker, keyboard_builder, idle_monitoring_enabled_getter):
        super().__init__(facade, admin_checker, keyboard_builder)
        self.get_idle_monitoring_enabled = idle_monitoring_enabled_getter
    
    async def start_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработчик команды /start"""
        user = update.effective_user
        chat = update.effective_chat

        if chat.type == "private":
            show_admin = self.is_admin(user.id)
            welcome_text = (
                "👋 Привет! Я бот для управления Minecraft сервером.\n\n"
                "📋 Доступные команды:\n"
                "/status - статус сервера\n"
                "/players - список игроков онлайн\n"
                "/balance - информация о балансе VPS\n"
                "/help - справка по всем командам\n"
            )
            if show_admin:
                welcome_text += (
                    "\n👑 Команды для администраторов:\n"
                    "/start_server - запустить сервер\n"
                    "/stop_server - остановить сервер\n"
                    "/restart_server - перезагрузить сервер\n"
                    "/settings - настройки автовыключения\n"
                    "/add_admin <id> - добавить администратора\n"
                    "/list_admins - список администраторов\n"
                    "/del_admin <id> - удалить администратора\n"
                )
            welcome_text += "\n💡 Используйте кнопки ниже для быстрого управления:"
            keyboard = await self.get_keyboard(show_admin)
            await update.message.reply_text(welcome_text, reply_markup=keyboard)
        else:
            keyboard = await self.get_keyboard(False)
            await update.message.reply_text(
                "🤖 Бот Minecraft сервера активен.\n"
                "Используйте /players для проверки игроков онлайн.",
                reply_markup=keyboard
            )

    async def help_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработчик команды /help"""
        user = update.effective_user
        show_admin = self.is_admin(user.id)
        
        help_text = (
            "📋 <b>Доступные команды:</b>\n\n"
            "<b>Для всех пользователей:</b>\n"
            "• /start - главное меню\n"
            "• /status - статус сервера\n"
            "• /players - список игроков онлайн\n"
            "• /balance - информация о балансе VPS\n"
            "• /help - эта справка\n"
            "• /ping - проверка работы бота\n"
        )
        
        if show_admin:
            help_text += (
                "\n<b>👑 Для администраторов (только в ЛС):</b>\n"
                "• /start_server - запустить сервер\n"
                "• /stop_server - остановить сервер\n"
                "• /restart_server - перезагрузить сервер\n"
                "• /settings - управление настройками\n"
                "• /add_admin &lt;id&gt; - добавить администратора\n"
                "• /del_admin &lt;id&gt; - удалить администратора\n"
                "• /list_admins - список администраторов\n"
                "\n<b>🎛️ Доступные кнопки:</b>\n"
                "• 📊 Статус - текущий статус сервера\n"
                "• 💵 Пополнить - информация о пополнении\n"
                "• ▶️ Запустить - запуск сервера\n"
                "• ⏹️ Остановить - остановка сервера\n"
                "• 🔄 Перезагрузить - перезагрузка сервера\n"
                "• ⚙️ Настройки - управление автовыключением\n"
            )
        else:
            help_text += (
                "\n<b>🎛️ Доступные кнопки:</b>\n"
                "• 📊 Статус - текущий статус сервера\n"
                "• 💵 Пополнить - информация о пополнении\n"
            )
        
        await update.message.reply_text(help_text, parse_mode="HTML")

    async def status_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработчик команды /status"""
        user = update.effective_user
        show_admin = self.is_admin(user.id) and update.effective_chat.type == "private"

        keyboard = await self.get_keyboard(show_admin)
        msg = await update.message.reply_text("⏳ Проверяю статус...", reply_markup=keyboard)

        result = await self.facade.status()
        text = ServerStatus.format_server_status(result, monitoring_enabled=self.get_idle_monitoring_enabled())

        keyboard = await self.get_keyboard(show_admin)
        await msg.edit_text(
            text,
            reply_markup=keyboard,
            parse_mode="HTML",
            disable_web_page_preview=True
        )

    async def players_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработчик команды /players (доступна всем)"""
        status_msg = await update.message.reply_text(
            "⏳ Проверяю статус сервера...",
            parse_mode="HTML",
            disable_web_page_preview=True
        )

        try:
            status: ServerStatus = await self.facade.status()
        except Exception as e:
            await status_msg.edit_text(
                f"❌ Ошибка при получении статуса: {e}",
                parse_mode="HTML",
                disable_web_page_preview=True
            )
            return

        if status.state != ServerState.READY:
            text = ServerStatus.format_server_status(status, monitoring_enabled=self.get_idle_monitoring_enabled())
            await status_msg.edit_text(
                f"{text}\n🎮 Minecraft: не запущен",
                parse_mode="HTML",
                disable_web_page_preview=True
            )
            return

        text = ServerStatus.format_players(status)
        await status_msg.edit_text(text, parse_mode="HTML", disable_web_page_preview=True)

    async def ping_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Проверка работы бота"""
        await update.message.reply_text("🏓 Понг! Бот работает.")


def register_info_handlers(app: Application, facade, is_admin_checker, keyboard_builder, idle_monitoring_getter):
    """Регистрирует информационные команды"""
    commands = InfoCommands(facade, is_admin_checker, keyboard_builder, idle_monitoring_getter)
    
    app.add_handler(CommandHandler("start", commands.start_command))
    app.add_handler(CommandHandler("help", commands.help_command))
    app.add_handler(CommandHandler("status", commands.status_command))
    app.add_handler(CommandHandler("players", commands.players_command))
    app.add_handler(CommandHandler("ping", commands.ping_command))
    
    logger.info("✅ Информационные команды зарегистрированы")
