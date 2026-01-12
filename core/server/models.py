from dataclasses import dataclass
from typing import Optional


@dataclass
class ActionResult:
    action_id: Optional[str]
    status: str  # new | in-progress | completed | errored | locked


@dataclass
class ServerStatus:
    vps_status: str        # on / off
    minecraft_active: bool
    players: int
    ip: Optional[str] = None
