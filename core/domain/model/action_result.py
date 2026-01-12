# core/domain/model/action_result.py
from dataclasses import dataclass
from typing import Optional

@dataclass
class ActionResult:
    action_id: Optional[str] | None
    status: str  # new | in-progress | completed | errored | locked
