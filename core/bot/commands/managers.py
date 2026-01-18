"""
Менеджеры для управления операциями, админами и настройками
"""
import asyncio
import logging
from telegram import InlineKeyboardMarkup

logger = logging.getLogger(__name__)


class OperationManager:
    """Управление операциями с сервером"""
    
    def __init__(self, active_operations_dict, perform_operation_callback):
        self.active_operations = active_operations_dict
        self.perform_operation = perform_operation_callback
        
    def is_active(self, chat_id: int) -> bool:
        """Проверяет, активна ли операция"""
        return chat_id in self.active_operations
        
    async def start_operation(self, operation_type: str, chat_id: int, message_id: int, show_admin: bool):
        """Запускает операцию"""
        task = asyncio.create_task(
            self.perform_operation(operation_type, chat_id, message_id, show_admin)
        )
        
        self.active_operations[chat_id] = {
            'task': task,
            'operation_type': operation_type,
            'message_id': message_id
        }


class AdminManager:
    """Управление администраторами"""
    
    def __init__(self, admin_ids_set, save_callback):
        self.admin_ids = admin_ids_set
        self.save_admins = save_callback
        
    def add_admin(self, admin_id: int):
        """Добавляет администратора"""
        self.admin_ids.add(admin_id)
        self.save_admins()
        
    def remove_admin(self, admin_id: int) -> bool:
        """Удаляет администратора"""
        if admin_id in self.admin_ids:
            self.admin_ids.remove(admin_id)
            self.save_admins()
            return True
        return False
        
    def get_admins(self):
        """Возвращает список администраторов"""
        return self.admin_ids


class SettingsManager:
    """Управление настройками"""
    
    def __init__(self, toggle_callback, is_enabled_getter, keyboard_getter):
        self.toggle_auto_shutdown = toggle_callback
        self.is_enabled = is_enabled_getter
        self.get_keyboard = keyboard_getter
        
    def is_auto_shutdown_enabled(self) -> bool:
        """Проверяет, включено ли автовыключение"""
        return self.is_enabled()
        
    def get_settings_keyboard(self) -> InlineKeyboardMarkup:
        """Возвращает клавиатуру настроек"""
        return self.get_keyboard()
