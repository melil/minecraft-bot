"""
Команды для общения между Telegram и Minecraft
"""
import logging
from telegram import Update
from telegram.ext import CommandHandler, ContextTypes

logger = logging.getLogger(__name__)


def register_chat_handlers(
    application,
    facade,
    is_admin_func,
    is_super_admin_func,
    keyboard_builder,
    minecraft_ssh_config,
    monitoring_enabled_func,
    register_user_func,
    register_group_func
):
    """
    Регистрирует обработчики команд общения с Minecraft
    """
    
    async def say_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
        """
        Отправляет сообщение в игровой чат Minecraft
        Использование: /say <сообщение>
        """
        user = update.effective_user
        chat = update.effective_chat
        
        # Register user and group
        register_user_func(user)
        if chat.type in ["group", "supergroup"]:
            register_group_func(chat)
        
        # Проверка прав: только админы могут отправлять сообщения
        if not is_admin_func(user.id):
            await update.message.reply_text(
                "❌ У вас нет прав для использования этой команды.\n"
                "Только администраторы могут отправлять сообщения в Minecraft чат."
            )
            return
        
        # Проверяем, что указан текст сообщения
        if not context.args:
            await update.message.reply_text(
                "❌ Укажите текст сообщения.\n\n"
                "Использование: /say <сообщение>\n"
                "Пример: /say Привет всем!"
            )
            return
        
        # Собираем сообщение из аргументов
        message = " ".join(context.args)
        
        # Получаем имя отправителя
        sender_name = user.username or user.first_name or f"User{user.id}"
        
        # Проверяем, что сервер запущен
        try:
            from core.minecraft.service import is_ready
            server_ready = await is_ready(minecraft_ssh_config)
            
            if not server_ready:
                await update.message.reply_text(
                    "❌ Minecraft сервер не запущен.\n"
                    "Сначала запустите сервер командой /start"
                )
                return
            
            # Отправляем сообщение через RCON
            from core.minecraft.rcon import say
            
            success = await say(minecraft_ssh_config, message, sender=sender_name)
            
            if success:
                await update.message.reply_text(
                    f"✅ Сообщение отправлено в Minecraft чат!\n\n"
                    f"📤 <b>От:</b> {sender_name}\n"
                    f"💬 <b>Текст:</b> {message}",
                    parse_mode="HTML"
                )
                logger.info(f"✉️ {sender_name} отправил сообщение в MC: {message}")
            else:
                await update.message.reply_text(
                    "❌ Не удалось отправить сообщение.\n"
                    "Возможно, RCON недоступен или сервер перезагружается."
                )
                
        except Exception as e:
            logger.error(f"Ошибка при отправке сообщения в Minecraft: {e}")
            await update.message.reply_text(
                f"❌ Ошибка при отправке сообщения: {e}"
            )
    
    async def mc_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
        """
        Альтернативная команда для отправки сообщений (более короткая)
        Использование: /mc <сообщение>
        """
        # Перенаправляем на say_command
        await say_command(update, context)
    
    async def rcon_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
        """
        Выполняет произвольную RCON команду (только для супер-админов)
        Использование: /rcon <команда>
        """
        user = update.effective_user
        chat = update.effective_chat
        
        # Register user and group
        register_user_func(user)
        if chat.type in ["group", "supergroup"]:
            register_group_func(chat)
        
        # Проверка прав: только супер-админы
        if not is_super_admin_func(user.id):
            await update.message.reply_text(
                "❌ У вас нет прав для использования этой команды.\n"
                "Команда /rcon доступна только супер-администраторам."
            )
            return
        
        # Проверяем, что указана команда
        if not context.args:
            await update.message.reply_text(
                "❌ Укажите RCON команду.\n\n"
                "Использование: /rcon <команда>\n"
                "Примеры:\n"
                "  /rcon list - список игроков\n"
                "  /rcon time set day - установить день\n"
                "  /rcon weather clear - очистить погоду"
            )
            return
        
        # Собираем команду из аргументов
        command = " ".join(context.args)
        
        # Проверяем, что сервер запущен
        try:
            from core.minecraft.service import is_ready
            server_ready = await is_ready(minecraft_ssh_config)
            
            if not server_ready:
                await update.message.reply_text(
                    "❌ Minecraft сервер не запущен."
                )
                return
            
            # Выполняем RCON команду
            from core.minecraft.rcon import execute_rcon_command
            
            result = await execute_rcon_command(minecraft_ssh_config, command)
            
            if result:
                # Ограничиваем длину ответа
                if len(result) > 4000:
                    result = result[:4000] + "... (обрезано)"
                
                await update.message.reply_text(
                    f"✅ Команда выполнена:\n\n"
                    f"<code>{command}</code>\n\n"
                    f"📋 <b>Ответ:</b>\n<pre>{result}</pre>",
                    parse_mode="HTML"
                )
                logger.info(f"🎮 {user.username or user.id} выполнил RCON: {command}")
            else:
                await update.message.reply_text(
                    "❌ Не удалось выполнить команду.\n"
                    "Возможно, RCON недоступен."
                )
                
        except Exception as e:
            logger.error(f"Ошибка при выполнении RCON команды: {e}")
            await update.message.reply_text(f"❌ Ошибка: {e}")
    
    # Регистрируем обработчики
    application.add_handler(CommandHandler("say", say_command))
    application.add_handler(CommandHandler("mc", mc_command))
    application.add_handler(CommandHandler("rcon", rcon_command))
    
    logger.info("✅ Chat handlers registered")
