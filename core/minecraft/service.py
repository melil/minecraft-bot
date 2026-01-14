# core/minecraft/service.py
import re
from typing import List, Tuple

from core.config import BOT_DIRECTORY
from core.ssh.client import run

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


def clean_name(name: str) -> str:
    """Убирает ANSI escape-последовательности из имени"""
    ansi_escape = re.compile(r'\x1B\[[0-?]*[ -/]*[@-~]')
    return ansi_escape.sub('', name).strip()

#todo: migrate to html and after migrate to DB
def format_player_name_md(name: str) -> str:
    PLAYER_ID_MAP = {
        "Trudovick": 78120051,
        "PAPIN_TYZ": 505878676,
        "orlan1211": 860938417,
        "_zari_1": 451548653,
        "_SoftEclipse_": 851242077,
        "aziatov": 138349349,
        "nice_korew25": 140821964,
    }

    user_id = PLAYER_ID_MAP.get(name)

    if user_id:
        # ВАЖНО: без escape_md
        return f"[{escape_md(name)}](tg://user?id={user_id})"
    else:
        # А вот тут можно экранировать, если без ссылки
        return escape_md(name)

def escape_md(text: str) -> str:
    # Минимум, который реально ломает Markdown
    return (
        text
        .replace("_", r"\_")
        .replace("[", r"\[")
        .replace("]", r"\]")
        .replace("(", r"\(")
        .replace(")", r"\)")
    )


async def players_with_names_count() -> Tuple[int, int, List[str]]:
    """
    Возвращает кортеж:
    (текущее кол-во игроков, максимум, список имён (italic + tg-ссылки)).
    Если ошибка, возвращает (-1, -1, []).
    """
    output = await run("/root/scripts/players.sh")
    print(f"players output: {output}")

    if not output or "❌" in output:
        return -1, -1, []

    match = re.search(r"There are (\d+) of a max of (\d+) players online", output)
    if not match:
        return -1, -1, []

    current = int(match.group(1))
    maximum = int(match.group(2))

    names_part = output.split(":", 1)[-1].strip()

    raw_names = (
        [clean_name(name) for name in names_part.split(",") if name.strip()]
        if names_part
        else []
    )

    names = [format_player_name_md(name) for name in raw_names]

    # если сервер вернул 0, но имена есть
    if current == 0 and names:
        current = len(names)

    return current, maximum, names



async def save_and_stop() -> str:
    return await run(f"bash {SCRIPTS_DIR}/stop_server_manually.sh")


async def save_and_prepare_reboot() -> str:
    return await run(f"bash {SCRIPTS_DIR}/reboot_server_manually.sh")