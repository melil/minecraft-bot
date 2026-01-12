# core/domain/model/server_state.py

from enum import StrEnum

class ServerState(StrEnum):
    OFF = "off"            # VPS выключен
    STARTING = "starting"  # VPS включается
    ON = "on"              # VPS включен, но MC может грузиться
    BOOTING = "booting"    # Minecraft запускается
    READY = "ready"        # Minecraft готов
    ERROR = "error"        # что-то пошло не так
