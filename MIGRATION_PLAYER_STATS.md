# Миграция базы данных: Таблица player_stats

## Описание

Эта миграция добавляет таблицу `player_stats` для хранения статистики игроков Minecraft.

## Что добавляется

### Таблица player_stats

| Поле | Тип | Описание |
|------|-----|----------|
| `id` | Integer | Первичный ключ |
| `minecraft_uuid` | String(36) | UUID игрока (уникальный, индекс) |
| `minecraft_nickname` | String(16) | Никнейм игрока (индекс) |
| `playtime_ticks` | BigInteger | Время игры в тиках (20 тиков = 1 сек) |
| `deaths` | Integer | Количество смертей |
| `mob_kills` | Integer | Количество убитых мобов |
| `jumps` | Integer | Количество прыжков |
| `last_updated` | DateTime | Время последнего обновления |
| `first_seen` | DateTime | Время первого захода |
| `last_seen` | DateTime | Время последнего захода |

## Как применить миграцию

### Вариант 1: Автоматическая миграция (рекомендуется)

```bash
# Применить миграцию
python migrate_player_stats.py

# Проверить статус без изменений
python migrate_player_stats.py --check
```

### Вариант 2: Через бот

Таблица создастся автоматически при первом запуске бота, так как используется SQLAlchemy с `Base.metadata.create_all()`.

```bash
python bot.py
```

## Проверка миграции

```bash
# Проверить, создана ли таблица
python migrate_player_stats.py --check
```

Или через SQLite напрямую:

```bash
sqlite3 bot.db

# Посмотреть структуру таблицы
.schema player_stats

# Посмотреть данные
SELECT * FROM player_stats LIMIT 5;

# Выход
.quit
```

## Откат миграции (если нужно)

Если нужно удалить таблицу:

```bash
sqlite3 bot.db "DROP TABLE IF EXISTS player_stats;"
```

Или через Python:

```python
from core.database import get_db

db = get_db()
db.engine.execute("DROP TABLE IF EXISTS player_stats")
```

## Тестирование

После применения миграции проверьте работу команд:

```bash
# Запустите бот
python bot.py
```

В Telegram:
1. `/stats PlayerName` - статистика игрока
2. `/top_playtime` - топ игроков
3. Нажмите "📈 Статистика" в главном меню

## Возможные проблемы

### Проблема: Таблица уже существует

**Решение:** Миграция проверяет наличие таблицы и не создаст дубликат.

### Проблема: Ошибка доступа к базе данных

**Решение:** 
- Убедитесь, что файл `bot.db` не открыт в других программах
- Проверьте права доступа к файлу

### Проблема: Отсутствуют колонки

**Решение:**
```bash
# Удалите старую таблицу и создайте заново
sqlite3 bot.db "DROP TABLE player_stats;"
python migrate_player_stats.py
```

## Резервное копирование

Перед миграцией рекомендуется сделать backup:

```bash
# Создать backup базы данных
cp bot.db bot.db.backup.$(date +%Y%m%d_%H%M%S)

# Или
sqlite3 bot.db ".backup bot.db.backup"
```

## После миграции

После успешной миграции вы можете:

1. **Использовать команды статистики:**
   - `/stats` - своя статистика
   - `/stats <ник>` - статистика игрока  
   - `/top_playtime` - топ игроков
   - `/stats_all` - общая статистика (админы)

2. **Использовать интерактивное меню:**
   - Нажмите "📈 Статистика" в главном меню
   - Выберите игрока из списка
   - Посмотрите топ игроков

3. **Проверить кэширование:**
   - Первый запрос загружает данные с сервера
   - Повторные запросы используют кэш (5-10 минут)
   - Кэш автоматически обновляется

## Структура данных

Статистика собирается из файлов Minecraft:
- **Источник:** `/root/freshcraft_industrial_server/world/stats/<UUID>.json`
- **Кэш:** Таблица `player_stats` в SQLite
- **Обновление:** При каждом запросе, если кэш устарел

## Дополнительная информация

- **Формат UUID:** `xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx` (36 символов)
- **Никнейм:** До 16 символов
- **Время игры:** Хранится в тиках, отображается в часах/минутах
- **Индексы:** По `minecraft_uuid` (уникальный) и `minecraft_nickname` для быстрого поиска

## Логи

Миграция выводит подробные логи:
```
🚀 Starting player_stats table migration...
📝 Creating 'player_stats' table...
✅ Table 'player_stats' created successfully
📊 player_stats table structure:
  • id                  INTEGER         NOT NULL
  • minecraft_uuid      VARCHAR(36)     NOT NULL
  ...
✅ Migration completed successfully!
```

---

**Дата создания:** 2026-01-19  
**Версия:** 1.0  
**Автор:** Minecraft Bot Team
