# core/minecraft/service.py
import re
from typing import List

from core.domain.model.action_result import ActionResult
from core.ssh.client import run, is_available
from core.config import BOT_DIRECTORY

SCRIPTS_DIR = f"{BOT_DIRECTORY}/scripts"


async def is_service_active() -> bool:
    """
    Проверяет, что systemd-сервис minecraft запущен
    """
    output = await run("systemctl is-active minecraft || true")
    print(f"is_service_active: {output}")
    return output.strip() == "active"


async def is_rcon_ready() -> bool:
    """
    Проверяет, что Minecraft отвечает по RCON
    """
    output = await run("/root/scripts/players.sh")

    if not output:
        return False

    if "❌" in output:
        return False

    # mcrcon list обычно возвращает:
    # There are 0 of a max of 20 players online:
    print(f"is_rcon_ready: {output}")
    return "There are" in output


async def is_ready() -> bool:
    """
    Minecraft полностью готов принимать игроков
    """
    if not await is_service_active():
        return False

    return await is_rcon_ready()


async def players_count() -> int:
    output = await run("/root/scripts/players.sh")
    print(f"players count: {output}")
    print(f"scriptDir: {SCRIPTS_DIR}")
    if not output or "❌" in output:
        return -1

    match = re.search(r"There are (\d+) of a max", output)
    if match:
        return int(match.group(1))

    if "There are 0" in output:
        return 0

    return -1


async def players_with_names_count() -> tuple[int, int, List[str]]:
    """
    Возвращает кортеж: (текущее кол-во игроков, максимум, список имён).
    Если ошибка, возвращает (-1, -1, []).
    """
    output = await run("/root/scripts/players.sh")
    print(f"players output: {output}")

    if not output or "❌" in output:
        return -1, -1, []

    # Пример строки:
    # "There are 0 of a max of 20 players online: asd,jake,hansen"
    match = re.search(r"There are (\d+) of a max of (\d+) players online", output)
    if match:
        current = int(match.group(1))
        maximum = int(match.group(2))

        # Получаем имена после двоеточия
        names_part = output.split(":", 1)[-1].strip()
        if names_part:
            names = [name.strip() for name in names_part.split(",") if name.strip()]
        else:
            names = []

        return current, maximum, names

    return -1, -1, []


async def save_and_stop() -> str:
    return await run(f"bash {SCRIPTS_DIR}/stop_server_manually.sh")


async def save_and_prepare_reboot() -> str:
    return await run(f"bash {SCRIPTS_DIR}/reboot_server_manually.sh")