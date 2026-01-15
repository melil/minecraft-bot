from dataclasses import dataclass
from typing import Optional


@dataclass
class ActionResult:
    """Результат выполнения действия"""
    status: str  # "success", "error", "locked"
    message: str
    action_id: Optional[str] = None  # ID действия в REG.RU API