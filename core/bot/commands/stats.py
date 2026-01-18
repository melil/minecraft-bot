"""
Команды для работы со статистикой игроков
"""
import logging
from telegram import Update
from telegram.ext import CommandHandler, ContextTypes
from datetime import datetime

logger = logging.getLogger(__name__)


async def stats_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Команда /stats [nickname]
    Показывает статистику игрока
    """
    from core.config import MINECRAFT_SERVER_SSH
    from core.minecraft.stats import (
        get_player_stats,
        find_player_by_nickname,
        format_playtime
    )
    from core.database import get_db
    
    db = get_db()
    user = update.effective_user
    
    # Регистрируем пользователя
    context.bot_data.get('register_user', lambda x: None)(user)
    
    await update.message.reply_text("⏳ Загружаю статистику...")
    
    try:
        # Определяем, чью статистику показывать
        nickname = None
        if context.args and len(context.args) > 0:
            # Указан никнейм в аргументе
            nickname = context.args[0]
        else:
            # Ищем привязанный никнейм в БД
            db_user = db.get_user_by_telegram_id(user.id)
            if db_user and db_user.minecraft_nickname:
                nickname = db_user.minecraft_nickname
            else:
                await update.message.reply_text(
                    "❌ Укажите никнейм игрока:\n"
                    "<code>/stats &lt;никнейм&gt;</code>\n\n"
                    "Или попросите админа привязать ваш Minecraft никнейм к вашему Telegram аккаунту.",
                    parse_mode="HTML"
                )
                return
        
        # Проверяем кэш
        cached = db.get_cached_player_stats_by_nickname(nickname, cache_minutes=5)
        if cached:
            logger.info(f"📦 Используем кэшированную статистику для {nickname}")
            stats = {
                'nickname': cached.minecraft_nickname,
                'playtime_ticks': cached.playtime_ticks,
                'deaths': cached.deaths,
                'mob_kills': cached.mob_kills,
                'jumps': cached.jumps,
            }
            stats['playtime_formatted'] = format_playtime_from_ticks(cached.playtime_ticks)
        else:
            # Ищем UUID игрока
            logger.info(f"🔍 Ищем UUID для {nickname}")
            result = await find_player_by_nickname(MINECRAFT_SERVER_SSH, nickname)
            
            if not result:
                await update.message.reply_text(
                    f"❌ Игрок <b>{nickname}</b> не найден на сервере.\n\n"
                    "Возможно, он никогда не заходил на сервер.",
                    parse_mode="HTML"
                )
                return
            
            player_uuid, exact_nickname = result
            logger.info(f"✅ Найден UUID: {player_uuid}, точный никнейм: {exact_nickname}")
            
            # Загружаем статистику с сервера
            stats = await get_player_stats(MINECRAFT_SERVER_SSH, player_uuid, exact_nickname)
            
            if not stats:
                await update.message.reply_text(
                    f"❌ Не удалось загрузить статистику для <b>{exact_nickname}</b>",
                    parse_mode="HTML"
                )
                return
            
            # Сохраняем в кэш
            db.update_player_stats(
                minecraft_uuid=player_uuid,
                minecraft_nickname=stats['nickname'],
                playtime_ticks=stats['playtime_ticks'],
                deaths=stats.get('deaths', 0),
                mob_kills=stats.get('mob_kills', 0),
                jumps=stats.get('jumps', 0),
                last_seen=datetime.utcnow()
            )
            logger.info(f"💾 Статистика для {stats['nickname']} сохранена в кэш")
        
        # Формируем сообщение
        message = (
            f"📊 <b>Статистика игрока {stats['nickname']}</b>\n\n"
            f"⏱️ <b>Время в игре:</b> {stats['playtime_formatted']}\n"
            f"💀 <b>Смертей:</b> {stats.get('deaths', 0)}\n"
            f"⚔️ <b>Убито мобов:</b> {stats.get('mob_kills', 0)}\n"
            f"🦘 <b>Прыжков:</b> {stats.get('jumps', 0)}\n"
        )
        
        await update.message.reply_text(message, parse_mode="HTML")
        
    except Exception as e:
        logger.error(f"❌ Ошибка в команде /stats: {e}", exc_info=True)
        await update.message.reply_text(
            f"❌ Произошла ошибка при загрузке статистики:\n<code>{str(e)}</code>",
            parse_mode="HTML"
        )


async def top_playtime_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Команда /top_playtime
    Показывает топ игроков по времени игры
    """
    from core.config import MINECRAFT_SERVER_SSH
    from core.minecraft.stats import get_top_players_by_playtime, format_playtime
    from core.database import get_db
    
    db = get_db()
    user = update.effective_user
    
    # Регистрируем пользователя
    context.bot_data.get('register_user', lambda x: None)(user)
    
    await update.message.reply_text("⏳ Загружаю топ игроков...")
    
    try:
        # Определяем лимит
        limit = 10
        if context.args and len(context.args) > 0:
            try:
                limit = int(context.args[0])
                limit = max(1, min(limit, 25))  # От 1 до 25
            except ValueError:
                pass
        
        # Проверяем, есть ли свежий кэш (последнее обновление менее 10 минут назад)
        cached_players = db.get_top_players_by_playtime(limit=limit)
        
        use_cache = False
        if cached_players:
            # Проверяем свежесть кэша
            latest_update = max(p.last_updated for p in cached_players)
            cache_age = (datetime.utcnow() - latest_update).total_seconds() / 60
            
            if cache_age < 10:
                use_cache = True
                logger.info(f"📦 Используем кэшированный топ (обновлен {cache_age:.1f} мин назад)")
        
        if use_cache:
            # Используем кэшированные данные
            top_players = [
                {
                    'nickname': p.minecraft_nickname or 'Unknown',
                    'playtime_ticks': p.playtime_ticks,
                    'playtime_formatted': format_playtime_from_ticks(p.playtime_ticks)
                }
                for p in cached_players
            ]
        else:
            # Загружаем свежие данные с сервера
            logger.info(f"🔄 Загружаем свежую статистику с сервера")
            top_players = await get_top_players_by_playtime(MINECRAFT_SERVER_SSH, limit=limit)
            
            if not top_players:
                await update.message.reply_text(
                    "❌ Не удалось загрузить статистику игроков"
                )
                return
            
            # Обновляем кэш
            for player in top_players:
                db.update_player_stats(
                    minecraft_uuid=player['uuid'],
                    minecraft_nickname=player['nickname'],
                    playtime_ticks=player['playtime_ticks'],
                    deaths=player.get('deaths', 0),
                    mob_kills=player.get('mob_kills', 0),
                    jumps=player.get('jumps', 0)
                )
            logger.info(f"💾 Кэш обновлен для {len(top_players)} игроков")
        
        # Формируем сообщение
        if not top_players:
            await update.message.reply_text("❌ На сервере еще не было игроков")
            return
        
        message_lines = [f"🏆 <b>Топ {len(top_players)} игроков по времени игры</b>\n"]
        
        medals = ["🥇", "🥈", "🥉"]
        for i, player in enumerate(top_players, 1):
            medal = medals[i-1] if i <= 3 else f"{i}."
            nickname = player['nickname']
            playtime = player['playtime_formatted']
            
            message_lines.append(f"{medal} <b>{nickname}</b> — {playtime}")
        
        message = "\n".join(message_lines)
        await update.message.reply_text(message, parse_mode="HTML")
        
    except Exception as e:
        logger.error(f"❌ Ошибка в команде /top_playtime: {e}", exc_info=True)
        await update.message.reply_text(
            f"❌ Произошла ошибка:\n<code>{str(e)}</code>",
            parse_mode="HTML"
        )


async def stats_all_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Команда /stats_all (только для админов)
    Показывает краткую статистику всех игроков
    """
    from core.config import MINECRAFT_SERVER_SSH
    from core.minecraft.stats import get_all_players_stats
    from core.database import get_db
    
    db = get_db()
    user = update.effective_user
    
    # Регистрируем пользователя
    context.bot_data.get('register_user', lambda x: None)(user)
    
    # Проверяем права
    is_admin_func = context.bot_data.get('is_admin', lambda x: False)
    if not is_admin_func(user.id):
        await update.message.reply_text("❌ Эта команда доступна только администраторам")
        return
    
    await update.message.reply_text("⏳ Загружаю статистику всех игроков...")
    
    try:
        # Загружаем статистику
        all_players = await get_all_players_stats(MINECRAFT_SERVER_SSH)
        
        if not all_players:
            await update.message.reply_text("❌ На сервере еще не было игроков")
            return
        
        # Обновляем кэш
        for player in all_players:
            db.update_player_stats(
                minecraft_uuid=player['uuid'],
                minecraft_nickname=player['nickname'],
                playtime_ticks=player['playtime_ticks'],
                deaths=player.get('deaths', 0),
                mob_kills=player.get('mob_kills', 0),
                jumps=player.get('jumps', 0)
            )
        
        # Считаем статистику
        total_playtime = sum(p['playtime_ticks'] for p in all_players)
        total_deaths = sum(p.get('deaths', 0) for p in all_players)
        total_kills = sum(p.get('mob_kills', 0) for p in all_players)
        
        message = (
            f"📊 <b>Общая статистика сервера</b>\n\n"
            f"👥 <b>Всего игроков:</b> {len(all_players)}\n"
            f"⏱️ <b>Общее время игры:</b> {format_playtime_from_ticks(total_playtime)}\n"
            f"💀 <b>Всего смертей:</b> {total_deaths}\n"
            f"⚔️ <b>Убито мобов:</b> {total_kills}\n\n"
            f"Используйте /top_playtime для просмотра топа игроков"
        )
        
        await update.message.reply_text(message, parse_mode="HTML")
        
    except Exception as e:
        logger.error(f"❌ Ошибка в команде /stats_all: {e}", exc_info=True)
        await update.message.reply_text(
            f"❌ Произошла ошибка:\n<code>{str(e)}</code>",
            parse_mode="HTML"
        )


def format_playtime_from_ticks(ticks: int) -> str:
    """Вспомогательная функция для форматирования времени из тиков"""
    from core.minecraft.stats import ticks_to_timedelta, format_playtime
    return format_playtime(ticks_to_timedelta(ticks))


def register_stats_handlers(
    application,
    facade,
    is_admin,
    keyboard_builder,
    register_user,
    register_group
):
    """
    Регистрирует обработчики команд статистики
    
    Args:
        application: Telegram application
        facade: ServerFacade для управления сервером
        is_admin: Функция проверки прав админа
        keyboard_builder: Функция построения клавиатуры
        register_user: Функция регистрации пользователя
        register_group: Функция регистрации группы
    """
    # Сохраняем функции в bot_data для использования в командах
    application.bot_data['is_admin'] = is_admin
    application.bot_data['register_user'] = register_user
    application.bot_data['register_group'] = register_group
    
    # Регистрируем команды
    application.add_handler(CommandHandler("stats", stats_command))
    application.add_handler(CommandHandler("top_playtime", top_playtime_command))
    application.add_handler(CommandHandler("top", top_playtime_command))  # Алиас
    application.add_handler(CommandHandler("stats_all", stats_all_command))
    
    logger.info("✅ Stats handlers registered")
