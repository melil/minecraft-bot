# Быстрый старт: Миграция Player Stats

## TL;DR

```bash
# Применить миграцию
python migrate_player_stats.py

# Запустить бот
python bot.py

# Протестировать
python test_player_stats.py
```

## Шаги установки

### 1. Применить миграцию БД

```bash
# Проверить, нужна ли миграция
python migrate_player_stats.py --check

# Применить миграцию
python migrate_player_stats.py
```

**Вывод должен содержать:**
```
✅ Table 'player_stats' created successfully
✅ Migration completed successfully!
```

### 2. Запустить бот

```bash
python bot.py
```

### 3. Проверить работу

**В Telegram:**

1. Отправьте `/start` боту
2. Нажмите "📈 Статистика"
3. Выберите "👥 Выбрать игрока" или "🏆 Топ игроков"

**Или используйте команды:**
```
/stats PlayerName
/top_playtime
/top 15
```

## Что добавлено

### 📊 Новая таблица БД

- `player_stats` - хранит статистику игроков
- Автоматическое кэширование (5-10 минут)
- Индексы для быстрого поиска

### 🎮 Команды

- `/stats [ник]` - статистика игрока
- `/top_playtime [N]` - топ N игроков
- `/stats_all` - общая статистика (админы)

### 🖱️ Интерактивное меню

- Кнопка "📈 Статистика" в главном меню
- Выбор игрока из списка с пагинацией
- Просмотр топа игроков

### 📈 Метрики

- ⏱️ Время в игре
- 💀 Смерти
- ⚔️ Убийства мобов
- 🦘 Прыжки

## Тестирование

```bash
# Запустить тесты
python test_player_stats.py
```

Тесты проверяют:
- ✅ Создание/обновление записей
- ✅ Поиск по UUID/nickname
- ✅ Кэширование
- ✅ Топ игроков
- ✅ Загрузку данных с сервера (если доступен)

## Устранение проблем

### Таблица уже существует

```bash
# Это нормально, миграция пропустится
python migrate_player_stats.py --check
```

### База данных заблокирована

```bash
# Остановите бота и повторите
pkill -f bot.py
python migrate_player_stats.py
```

### Нет данных о игроках

Убедитесь, что:
- Сервер Minecraft доступен по SSH
- Путь к серверу правильный (`MINECRAFT_DIR` в `core/minecraft/stats.py`)
- Есть файлы в `world/stats/*.json`

### Проверка вручную

```bash
# Проверить таблицу
sqlite3 bot.db "SELECT * FROM player_stats LIMIT 5;"

# Посмотреть структуру
sqlite3 bot.db ".schema player_stats"

# Удалить таблицу (если нужно пересоздать)
sqlite3 bot.db "DROP TABLE player_stats;"
```

## Резервное копирование

```bash
# Перед миграцией
cp bot.db bot.db.backup

# Восстановление
cp bot.db.backup bot.db
```

## Дополнительно

Полная документация: [MIGRATION_PLAYER_STATS.md](MIGRATION_PLAYER_STATS.md)

## Поддержка

При проблемах проверьте логи:
```bash
# Логи миграции
python migrate_player_stats.py 2>&1 | tee migration.log

# Логи бота
python bot.py 2>&1 | tee bot.log
```
