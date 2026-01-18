"""
Команды баланса: balance
"""
import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, ContextTypes

from core.domain.model.server_state import ServerState
from .base import CommandBase

logger = logging.getLogger(__name__)


class BalanceCommands(CommandBase):
    """Команды баланса"""
    
    def __init__(self, facade, admin_checker, keyboard_builder, balance_keyboard_builder):
        super().__init__(facade, admin_checker, keyboard_builder)
        self.get_balance_keyboard = balance_keyboard_builder
    
    async def balance_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработчик команды /balance"""
        msg = await update.message.reply_text("⏳ Получаю информацию о балансе...")
        
        try:
            result = await self.facade.status()

            balance_text = (
                "⚙️ <b>Пополнение VPS</b>\n\n"
                f"Есть два варианта:\n"
                "<b>🟨.:Полуавтоматический</b>\n"
                "Банковская карта (номер, срок действия, cvv)\n"
                "Вы оплачиваете деньги на счет в Т-банк по ссылке, дальше я оплачиваю руками через ЛК\n\n"
                "<b>🟩.:Автоматический</b>\n"
                "СБП, Банковская карта, Ю-мани, Кэш, СберПей\n"
                f"Оплачивайте по ссылке введя айпи сервера <code>{result.ip}</code> (кликабельно) в поле ввода reg.cloud/prolong\n"
                "Средства будут зачислены автоматически\n\n"
                "Минимальная сумма пополнения: 100 ₽\n\n"
                f"Текущий баланс: {result.balance} ₽\n"
            )

            if result.state == ServerState.READY:
                balance_text += f"Стоимость в час: {result.hour_price} ₽\n\n"

            balance_text += "Используйте кнопки ниже для выбора:"
            
            # Получаем клавиатуру для пополнения
            keyboard = self.get_balance_keyboard()
            
            await msg.edit_text(
                balance_text,
                reply_markup=keyboard,
                parse_mode="HTML"
            )
        except Exception as e:
            logger.error(f"Ошибка при получении баланса: {e}")
            await msg.edit_text(f"❌ Ошибка при получении информации: {e}")


def register_balance_handlers(app: Application, facade, is_admin_checker, keyboard_builder, balance_keyboard_builder):
    """Регистрирует команды баланса"""
    commands = BalanceCommands(facade, is_admin_checker, keyboard_builder, balance_keyboard_builder)
    
    app.add_handler(CommandHandler("balance", commands.balance_command))
    
    logger.info("✅ Команды баланса зарегистрированы")
