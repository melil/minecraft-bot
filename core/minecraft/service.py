# core/minecraft/service.py
import re

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

async def players_count_and_names() -> tuple[int, list[str]]:
    output = await run("/root/scripts/players.sh")
    print(f"players output: {output}")
    print(f"scriptDir: {SCRIPTS_DIR}")

    if not output or "❌" in output:
        return -1, []

    # Попытка найти количество игроков и их имена
    match = re.search(
        r"There are (\d+) of a max of \d+ players online: (.+)", output
    )
    if match:
        count = int(match.group(1))
        # Разделяем ники по запятой и убираем лишние пробелы
        names = [name.strip() for name in match.group(2).split(",")]
        return count, names

    # Обработка случая с 0 игроками
    if "There are 0" in output:
        return 0, []

    return -1, []

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


async def save_and_stop() -> str:
    return await run(f"bash {SCRIPTS_DIR}/stop_server_manually.sh")


async def save_and_prepare_reboot() -> str:
    return await run(f"bash {SCRIPTS_DIR}/reboot_server_manually.sh")