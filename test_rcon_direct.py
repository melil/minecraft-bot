# test_rcon_direct.py
import asyncio
from core.ssh.client import SSHClient
from core.config import MINECRAFT_SERVER_SSH


async def test_rcon():
    print("🧪 Прямой тест RCON\n")

    client = SSHClient(**MINECRAFT_SERVER_SSH)

    MINECRAFT_DIR = "/root/freshcraft_industrial_server"

    # Тест команды
    print("Выполняю команду...")
    result = await client.execute(
        f"cd {MINECRAFT_DIR} && "
        f"RCON_PASS=$(grep 'rcon.password' server.properties | cut -d= -f2 | tr -d '\\r\\n') && "
        f"mcrcon -H 127.0.0.1 -P 25575 -p \"$RCON_PASS\" list 2>&1",
        timeout=10
    )

    print(f"Результат:\n{result}\n")

    # Парсинг
    if "There are" in result:
        import re
        lines = result.strip().split('\n')
        for line in lines:
            if "There are" in line:
                match = re.search(r'There are (\d+) of a max of (\d+) players online', line)
                if match:
                    current = int(match.group(1))
                    maximum = int(match.group(2))

                    if ':' in line:
                        names_part = line.split(':', 1)[1].strip()
                        names = [n.strip() for n in names_part.split(',')]
                        print(f"✅ Игроков: {current}/{maximum}")
                        print(f"✅ Имена: {names}")
                    else:
                        print(f"✅ Игроков: {current}/{maximum} (без имен)")


if __name__ == "__main__":
    asyncio.run(test_rcon())