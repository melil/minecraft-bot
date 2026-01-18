# 🤖 LameHorse Minecraft Bot для Telegram

Telegram бот для управления Minecraft сервером на REG.RU Cloud VPS с поддержкой двустороннего общения через RCON.

## 🎯 Основные возможности

### 🖥️ Управление сервером
- ▶️ Запуск/остановка/перезагрузка VPS сервера
- 📊 Мониторинг статуса сервера и Minecraft
- 👥 Отображение онлайн игроков с никнеймами
- 💰 Проверка баланса и стоимости сервера
- ⏱️ Автоматическое выключение при простое (0 игроков)
- ⏲️ Отображение uptime сервера

### 💬 Общение Telegram ↔ Minecraft (НОВОЕ!)
- 📤 **Отправка сообщений** из Telegram в игровой чат (`/say`, `/mc`)
- 🎮 **Выполнение RCON команд** (`/rcon`)
- 📥 **Получение событий** из Minecraft в Telegram:
  - ➕ Вход/выход игроков
  - 💬 Сообщения в игровом чате
  - 💀 Смерти игроков
  - 🏆 Достижения
- ⚙️ Гибкая настройка мониторинга событий

### 👥 Система пользователей
- 🔐 База данных пользователей (SQLite)
- 👑 Роли: User, Admin, Super Admin
- 🎮 Привязка Minecraft никнеймов к Telegram аккаунтам
- 📋 Управление правами доступа

### 🛡️ Группы и уведомления
- 📢 Поддержка работы в Telegram группах
- 🔔 Уведомления о событиях сервера
- 🎯 Настраиваемые уведомления

---

## 📦 Установка

### 1. Клонирование репозитория
```bash
git clone https://github.com/yourusername/minecraft-bot.git
cd minecraft-bot
```

### 2. Установка зависимостей
```bash
pip install -r requirements.txt
```

### 3. Настройка переменных окружения

Создайте файл `.env`:
```env
# Telegram Bot
TELEGRAM_TOKEN=your_telegram_bot_token

# REG.RU Cloud API
TIMEWEB_TOKEN=your_regru_api_token
MINECRAFT_SERVER_ID=your_server_id

# SSH доступ
MINECRAFT_SERVER_SSH=root@your-server-ip:22
MINECRAFT_SERVER_KEY_FILE=/path/to/ssh/key

# RCON (для общения с Minecraft)
MINECRAFT_RCON_PASSWORD=your_rcon_password
```

### 4. Настройка Minecraft сервера

Убедитесь, что RCON включен в `server.properties`:
```properties
enable-rcon=true
rcon.port=25575
rcon.password=your_rcon_password
```

Установите `mcrcon` на сервере:
```bash
apt install mcrcon
# или
git clone https://github.com/Tiiffi/mcrcon.git
cd mcrcon && make && cp mcrcon /usr/local/bin/
```

### 5. Запуск бота
```bash
python bot.py
```

### 6. Миграция базы данных (если обновляетесь)

Если вы обновляете бот и добавляете функционал статистики:

```bash
# Проверить статус миграции
python migrate_player_stats.py --check

# Применить миграцию
python migrate_player_stats.py
```

Подробнее см. [MIGRATION_PLAYER_STATS.md](MIGRATION_PLAYER_STATS.md)

---

## 🎮 Команды бота

### Основные команды
| Команда | Описание |
|---------|----------|
| `/start` | Показать главное меню |
| `/status` | Статус сервера |
| `/start_server` | Запустить сервер (админ) |
| `/stop_server` | Остановить сервер (админ) |
| `/restart_server` | Перезагрузить сервер (админ) |

### Общение с Minecraft
| Команда | Описание |
|---------|----------|
| `/say <текст>` | Отправить сообщение в игровой чат (админы) |
| `/mc <текст>` | Короткая версия `/say` (админы) |
| `/rcon <команда>` | Выполнить RCON команду (только супер-админы) |

**Примеры:**
```
/say Привет всем!
/mc Сервер будет перезагружен через 5 минут
/rcon time set day
/rcon weather clear
```

### Статистика игроков
| Команда | Описание |
|---------|----------|
| `/stats` | Показать свою статистику (требуется привязка ника) |
| `/stats <ник>` | Показать статистику указанного игрока |
| `/top_playtime` | Топ-10 игроков по времени игры |
| `/top <N>` | Топ-N игроков (максимум 25) |
| `/stats_all` | Общая статистика сервера (только админы) |

**Примеры:**
```
/stats
/stats PlayerName
/top_playtime
/top 15
```

### Админские команды
| Команда | Описание |
|---------|----------|
| `/add_admin <user_id>` | Добавить админа |
| `/remove_admin <user_id>` | Удалить админа |
| `/list_admins` | Список админов |
| `/set_nick <user_id> <nickname>` | Привязать MC никнейм |

---

## ⚙️ Настройки

### Автоматическое выключение
Сервер автоматически выключается через 5 минут простоя (0 игроков):
- Включить/выключить: `/start` → "⚙️ Настройки" → "⏱️ Автовыключение"
- Настроить таймаут в `bot.py`: `IDLE_SHUTDOWN_TIMEOUT = 600`

### Мониторинг событий Minecraft
События из игры автоматически отправляются в группу:
- Включить/выключить: `/start` → "⚙️ Настройки" → "📜 Мониторинг событий MC"
- Настроить типы событий в `bot.py`:
```python
MINECRAFT_EVENTS_CONFIG = {
    'join': True,      # Вход игроков
    'leave': True,     # Выход игроков
    'chat': True,      # Сообщения в чате
    'death': True,     # Смерти
    'achievement': True  # Достижения
}
```

### Уведомления
```python
# bot.py
ENABLE_ADMIN_NOTIFICATIONS = False  # Уведомления админам
ENABLE_GROUP_NOTIFICATIONS = True   # Уведомления в группу
NOTIFICATION_GROUP_ID = -1234567890 # ID группы
```

---

## 📚 Документация

- **[MINECRAFT_CHAT.md](MINECRAFT_CHAT.md)** - Подробная документация по общению Telegram ↔ Minecraft
- **[QUICKSTART_CHAT.md](QUICKSTART_CHAT.md)** - Быстрый старт для функционала общения
- **[DATABASE_UPGRADE.md](DATABASE_UPGRADE.md)** - Обновление базы данных
- **[MIGRATION_PLAYER_STATS.md](MIGRATION_PLAYER_STATS.md)** - Миграция для статистики игроков
- **[GROUP_SUPPORT.md](GROUP_SUPPORT.md)** - Поддержка групп
- **[MIGRATION.md](MIGRATION.md)** - Миграция на новую версию

---

## 🏗️ Архитектура

```
minecraft-bot/
├── bot.py                      # Главный файл бота
├── core/
│   ├── api/
│   │   └── regru.py           # REG.RU Cloud API клиент
│   ├── bot/
│   │   ├── commands/          # Модули команд
│   │   │   ├── admin.py       # Админские команды
│   │   │   ├── balance.py     # Команды баланса
│   │   │   ├── chat.py        # Команды общения с MC (NEW!)
│   │   │   ├── info.py        # Информационные команды
│   │   │   ├── server.py      # Управление сервером
│   │   │   └── settings.py    # Настройки
│   │   └── keyboards.py       # Telegram клавиатуры
│   ├── config.py              # Конфигурация
│   ├── database/
│   │   ├── database.py        # База данных
│   │   └── models.py          # Модели данных
│   ├── domain/
│   │   └── model/             # Доменные модели
│   ├── minecraft/
│   │   ├── service.py         # Minecraft сервисы
│   │   ├── rcon.py            # RCON клиент (NEW!)
│   │   └── log_monitor.py     # Мониторинг логов (NEW!)
│   ├── server/
│   │   └── facade.py          # Фасад управления сервером
│   └── ssh/
│       └── client.py          # SSH клиент
└── ops/
    └── scripts/               # Служебные скрипты
```

---

## 🚀 Основные фичи

### ✅ Реализовано
- [x] Управление VPS сервером (запуск/остановка/перезагрузка)
- [x] Мониторинг статуса Minecraft через RCON
- [x] Отображение списка игроков с никнеймами
- [x] Автоматическое выключение при простое
- [x] База данных пользователей с ролями
- [x] Поддержка групп Telegram
- [x] Отправка сообщений из Telegram в Minecraft
- [x] Выполнение RCON команд
- [x] Мониторинг событий из Minecraft (вход/выход, чат, смерти, достижения)
- [x] Уведомления в группу о событиях
- [x] Inline клавиатуры для управления
- [x] Статистика активности игроков (время игры, смерти, убийства мобов)
- [x] Топ игроков по времени игры

### 🔮 Планируется
- [ ] Графики и тренды активности
- [ ] Расширенная статистика (добытые блоки, пройденное расстояние)
- [ ] Backup системы миров
- [ ] Расписание запуска/остановки
- [ ] Веб-панель управления
- [ ] Поддержка нескольких серверов
- [ ] Интеграция с Discord

---

## 🛠️ Технологии

- **Python 3.10+**
- **python-telegram-bot** - Telegram Bot API
- **asyncio** - Асинхронное программирование
- **SQLite** - База данных
- **SSH/RCON** - Управление сервером
- **REG.RU Cloud API** - Управление VPS

---

## 🔒 Безопасность

- ✅ Роли и права доступа
- ✅ Хранение секретов в `.env`
- ✅ SSH ключи для доступа к серверу
- ✅ Экранирование команд RCON
- ✅ Логирование всех действий

---

## 🐛 Troubleshooting

### Бот не отвечает
```bash
# Проверьте логи
tail -f bot.log

# Проверьте токен Telegram
python -c "from core.config import TELEGRAM_TOKEN; print(TELEGRAM_TOKEN)"
```

### Сервер не запускается
```bash
# Проверьте API токен REG.RU
# Проверьте ID сервера
# Проверьте логи бота
```

### RCON не работает
```bash
# На сервере проверьте вручную:
mcrcon -H 127.0.0.1 -P 25575 -p your_password "say Test"

# Проверьте server.properties
grep rcon server.properties
```

### События не приходят
```bash
# Проверьте логи Minecraft
journalctl -u minecraft.service -n 50 --no-pager

# Включите мониторинг в настройках бота
```

---

## 📝 Лицензия

MIT License - делайте что хотите!

---

## 🤝 Вклад

Pull requests приветствуются! Для крупных изменений сначала откройте issue.

---

## 📞 Контакты

- Telegram: [@melil](https://t.me/melil)
- GitHub: [melil](https://github.com/melil)

---

## 🎉 Благодарности

- [python-telegram-bot](https://github.com/python-telegram-bot/python-telegram-bot)
- [mcrcon](https://github.com/Tiiffi/mcrcon)
- REG.RU Cloud

---

**Made with ❤️ for Minecraft community**
