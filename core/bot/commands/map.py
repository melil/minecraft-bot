"""
Команды для работы с BlueMap
"""
import logging
from telegram import Update
from telegram.ext import CommandHandler, ContextTypes

logger = logging.getLogger(__name__)


def register_map_handlers(
    application,
    bluemap_api,
    register_user_func,
    register_group_func
):
    """
    Регистрирует обработчики команд для работы с картой
    """
    
    async def map_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
        """
        Отправляет ссылку на веб-карту сервера
        Использование: /map
        """
        user = update.effective_user
        chat = update.effective_chat
        
        # Register user and group
        register_user_func(user)
        if chat.type in ["group", "supergroup"]:
            register_group_func(chat)
        
        map_url = bluemap_api.get_map_url()
        
        await update.message.reply_text(
            "🗺️ <b>Карта сервера</b>\n\n"
            f"Открыть веб-карту:\n{map_url}\n\n"
            "💡 <i>На карте видны игроки онлайн и все исследованные территории</i>",
            parse_mode="HTML",
            disable_web_page_preview=False
        )
        logger.info(f"📍 {user.username or user.id} запросил карту")
    
    async def where_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
        """
        Показывает местоположение игрока на карте
        Использование: /where <ник>
        """
        user = update.effective_user
        chat = update.effective_chat
        
        # Register user and group
        register_user_func(user)
        if chat.type in ["group", "supergroup"]:
            register_group_func(chat)
        
        # Проверяем аргументы
        if not context.args:
            await update.message.reply_text(
                "❌ Укажите ник игрока.\n\n"
                "Использование: /where <ник>\n"
                "Пример: /where Trudovick"
            )
            return
        
        player_name = context.args[0]
        
        # Получаем местоположение игрока
        player_data = await bluemap_api.get_player_location(player_name)
        
        if not player_data:
            await update.message.reply_text(
                f"❌ Игрок <b>{player_name}</b> не найден.\n\n"
                "Возможные причины:\n"
                "• Игрок не в сети\n"
                "• Неправильный ник",
                parse_mode="HTML"
            )
            return
        
        # Извлекаем координаты
        pos = player_data.get('position', {})
        x = int(pos.get('x', 0))
        y = int(pos.get('y', 0))
        z = int(pos.get('z', 0))
        world = player_data.get('world', 'world')
        
        # Генерируем ссылку на карту
        map_url = bluemap_api.get_map_url(x, y, z)
        
        await update.message.reply_text(
            f"📍 <b>{player_name}</b>\n\n"
            f"🌍 Мир: {world}\n"
            f"📊 Координаты: <code>{x}, {y}, {z}</code>\n\n"
            f"🗺️ <a href='{map_url}'>Смотреть на карте</a>",
            parse_mode="HTML",
            disable_web_page_preview=True
        )
        logger.info(f"📍 {user.username or user.id} запросил местоположение {player_name}")
    
    async def players_map_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
        """
        Показывает список всех игроков онлайн с их координатами
        Использование: /players_map
        """
        user = update.effective_user
        chat = update.effective_chat
        
        # Register user and group
        register_user_func(user)
        if chat.type in ["group", "supergroup"]:
            register_group_func(chat)
        
        # Получаем список игроков
        players = await bluemap_api.get_players()
        
        if not players:
            await update.message.reply_text(
                "👥 Сейчас никого нет на сервере.\n\n"
                f"🗺️ <a href='{bluemap_api.get_map_url()}'>Смотреть карту</a>",
                parse_mode="HTML",
                disable_web_page_preview=True
            )
            return
        
        # Формируем сообщение
        text = f"👥 <b>Игроки онлайн ({len(players)})</b>\n\n"
        
        for i, player in enumerate(players, 1):
            name = player.get('name', 'Unknown')
            pos = player.get('position', {})
            x = int(pos.get('x', 0))
            y = int(pos.get('y', 0))
            z = int(pos.get('z', 0))
            
            player_url = bluemap_api.get_map_url(x, y, z)
            text += f"{i}. <b>{name}</b>\n"
            text += f"   📊 <code>{x}, {y}, {z}</code>\n"
            text += f"   🗺️ <a href='{player_url}'>На карте</a>\n\n"
        
        text += f"🗺️ <a href='{bluemap_api.get_map_url()}'>Открыть полную карту</a>"
        
        await update.message.reply_text(
            text,
            parse_mode="HTML",
            disable_web_page_preview=True
        )
        logger.info(f"📍 {user.username or user.id} запросил список игроков на карте")
    
    # Регистрируем обработчики
    application.add_handler(CommandHandler("map", map_command))
    application.add_handler(CommandHandler("where", where_command))
    application.add_handler(CommandHandler("players_map", players_map_command))
    
    logger.info("✅ Map handlers registered")
