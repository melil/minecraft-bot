"""
Пакет команд для Telegram бота
"""
from .info import register_info_handlers
from .server import register_server_handlers
from .admin import register_admin_handlers
from .settings import register_settings_handlers
from .balance import register_balance_handlers

__all__ = [
    'register_info_handlers',
    'register_server_handlers',
    'register_admin_handlers',
    'register_settings_handlers',
    'register_balance_handlers'
]
