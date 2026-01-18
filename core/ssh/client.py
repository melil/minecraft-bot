import asyncio
import logging
from typing import Optional

logger = logging.getLogger(__name__)


class SSHClient:
    """
    Клиент для выполнения SSH команд на удаленном сервере
    """

    def __init__(self, user: str, host: str, port: int = 22, key_file: Optional[str] = None):
        """
        Args:
            user: имя пользователя SSH
            host: хост сервера
            port: порт SSH (по умолчанию 22)
            key_file: путь к приватному ключу (опционально)
        """
        self.user = user
        self.host = host
        self.port = port
        self.key_file = key_file
        self._connection_string = f"{user}@{host}"

        # Опции SSH для надежности
        self.ssh_options = [
            "-o", "ConnectTimeout=10",
            "-o", "StrictHostKeyChecking=no",
            "-o", "UserKnownHostsFile=/dev/null",
            "-o", "LogLevel=ERROR",
            "-p", str(port)
        ]

        if key_file:
            self.ssh_options.extend(["-i", key_file])

    async def execute(self, command: str, timeout: int = 20) -> str:
        """
        Выполняет команду через SSH

        Args:
            command: команда для выполнения
            timeout: таймаут выполнения в секундах

        Returns:
            str: результат выполнения команды

        Raises:
            TimeoutError: если команда выполняется слишком долго
            RuntimeError: если команда завершилась с ошибкой
        """
        try:
            # Формируем полную команду используя exec для лучшей обработки аргументов
            ssh_cmd = ["ssh"] + self.ssh_options + [self._connection_string, command]

            logger.debug(f"Выполнение SSH команды: {command[:100]}...")

            # Создаем процесс используя exec вместо shell для корректной работы с Unicode
            proc = await asyncio.create_subprocess_exec(
                *ssh_cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )

            # Ждем завершения с таймаутом
            try:
                stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout)
            except asyncio.TimeoutError:
                logger.error(f"SSH команда превысила таймаут {timeout}с: {command[:100]}")
                proc.kill()
                await proc.wait()
                raise TimeoutError(f"SSH команда превысила таймаут {timeout}с")

            # Декодируем вывод с поддержкой UTF-8
            try:
                result = stdout.decode('utf-8').strip()
                error_msg = stderr.decode('utf-8').strip()
            except UnicodeDecodeError:
                # Fallback на latin-1 если UTF-8 не работает
                result = stdout.decode('latin-1').strip()
                error_msg = stderr.decode('latin-1').strip()

            # Проверяем код возврата
            if proc.returncode != 0:
                logger.error(f"SSH команда завершилась с ошибкой (код {proc.returncode}): {error_msg}")
                # Для RCON команд код 1 может быть из-за проблем с кодировкой
                # Если есть результат в stdout, попробуем его использовать
                if result:
                    logger.warning(f"Есть результат несмотря на код ошибки: {result[:100]}")
                    return result
                raise RuntimeError(f"SSH error (код {proc.returncode}): {error_msg}")

            logger.debug(f"SSH команда выполнена успешно: {len(result)} байт")
            return result

        except (TimeoutError, RuntimeError):
            raise
        except Exception as e:
            logger.error(f"Неожиданная ошибка при выполнении SSH команды: {e}")
            raise RuntimeError(f"SSH exception: {e}")

    async def is_available(self) -> bool:
        """
        Проверяет доступность SSH соединения

        Returns:
            bool: True если сервер доступен, False иначе
        """
        try:
            result = await self.execute("echo SSH_OK", timeout=10)
            is_ok = "SSH_OK" in result

            if is_ok:
                logger.debug(f"SSH соединение с {self._connection_string} доступно")
            else:
                logger.warning(f"SSH соединение с {self._connection_string} недоступно")

            return is_ok
        except Exception as e:
            logger.error(f"Ошибка проверки доступности SSH {self._connection_string}: {e}")
            return False

    async def test_connection(self) -> dict:
        """
        Тестирует соединение и возвращает подробную информацию

        Returns:
            dict: {
                'available': bool,
                'latency_ms': float | None,
                'error': str | None
            }
        """
        import time

        try:
            start = time.time()
            result = await self.execute("echo SSH_OK", timeout=10)
            latency = (time.time() - start) * 1000  # в миллисекундах

            if "SSH_OK" in result:
                logger.info(f"SSH тест успешен: {self._connection_string} ({latency:.1f}ms)")
                return {
                    'available': True,
                    'latency_ms': round(latency, 1),
                    'error': None
                }
            else:
                return {
                    'available': False,
                    'latency_ms': None,
                    'error': "Неверный ответ от сервера"
                }

        except TimeoutError as e:
            logger.error(f"SSH тест: таймаут для {self._connection_string}")
            return {
                'available': False,
                'latency_ms': None,
                'error': str(e)
            }
        except Exception as e:
            logger.error(f"SSH тест: ошибка для {self._connection_string}: {e}")
            return {
                'available': False,
                'latency_ms': None,
                'error': str(e)
            }

    def __repr__(self):
        return f"SSHClient({self._connection_string}:{self.port})"


# ==================== ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ ====================

async def run_ssh_command(ssh_config: dict, command: str, timeout: int = 20) -> str:
    """
    Удобная обертка для выполнения одиночной SSH команды

    Args:
        ssh_config: словарь с параметрами SSH (host, user, port, key_file)
        command: команда для выполнения
        timeout: таймаут в секундах

    Returns:
        str: результат выполнения
    """
    client = SSHClient(**ssh_config)
    return await client.execute(command, timeout)


async def check_ssh_availability(ssh_config: dict) -> bool:
    """
    Проверяет доступность SSH

    Args:
        ssh_config: словарь с параметрами SSH

    Returns:
        bool: True если доступен
    """
    client = SSHClient(**ssh_config)
    return await client.is_available()