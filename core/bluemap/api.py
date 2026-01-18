"""
BlueMap API client
"""
import logging
import aiohttp
from typing import Optional, List, Dict, Any

logger = logging.getLogger(__name__)


class BlueMapAPI:
    """Client for BlueMap web API"""
    
    def __init__(self, base_url: str = "http://95.163.227.185:8100", ssh_config: dict = None):
        self.base_url = base_url.rstrip('/')
        self.ssh_config = ssh_config or {
            'host': '95.163.227.185',
            'user': 'root',
            'port': 22
        }
        
    async def get_players(self) -> List[Dict[str, Any]]:
        """
        Get list of online players with their positions
        
        Returns:
            List of player dicts with: name, uuid, position, world
        """
        try:
            async with aiohttp.ClientSession() as session:
                url = f"{self.base_url}/maps/world/live/players.json"
                async with session.get(url, timeout=10) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        # BlueMap format: {"players": [{"uuid": "", "name": "", "position": {...}}]}
                        return data.get('players', [])
                    else:
                        logger.error(f"BlueMap API error: {resp.status}")
                        return []
        except Exception as e:
            logger.error(f"Error fetching BlueMap players: {e}")
            return []
    
    async def get_player_location(self, player_name: str) -> Optional[Dict[str, Any]]:
        """
        Get specific player's location
        
        Args:
            player_name: Player's nickname
            
        Returns:
            Player data dict or None if not found
        """
        players = await self.get_players()
        for player in players:
            if player.get('name', '').lower() == player_name.lower():
                return player
        return None
    
    def get_map_url(self, x: Optional[int] = None, y: Optional[int] = None, z: Optional[int] = None) -> str:
        """
        Generate URL to BlueMap with optional coordinates
        
        Args:
            x, y, z: Coordinates to center on
            
        Returns:
            Full URL to BlueMap
        """
        if x is not None and y is not None and z is not None:
            # BlueMap URL format: #world:x:y:z:distance:pitch:yaw:0:0:perspective
            return f"{self.base_url}/#world:{x}:{y}:{z}:500:0:0:0:0:perspective"
        else:
            return f"{self.base_url}/"
    
    async def is_available(self) -> bool:
        """
        Check if BlueMap is available
        
        Returns:
            True if BlueMap responds
        """
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(self.base_url, timeout=5) as resp:
                    return resp.status == 200
        except:
            return False
    
    async def get_map_size(self, bluemap_path: str = "/root/freshcraft_industrial_server/bluemap") -> dict:
        """
        Get BlueMap directory size and stats via SSH
        
        Args:
            bluemap_path: Path to bluemap directory on server
            
        Returns:
            Dict with: size_mb, size_human, file_count
        """
        import asyncio
        from core.ssh.client import SSHClient
        
        try:
            logger.info(f"🔍 Начало проверки размера карты: {bluemap_path}")
            client = SSHClient(**self.ssh_config)
            
            # Проверяем, что папка существует
            cmd_check = f"[ -d {bluemap_path} ] && echo 'exists' || echo 'not_found'"
            result_check = await client.execute(cmd_check, timeout=5)
            
            if 'not_found' in result_check:
                logger.error(f"❌ Папка не найдена: {bluemap_path}")
                return {
                    'size_mb': 0,
                    'size_human': 'Unknown',
                    'file_count': 0,
                    'path': bluemap_path,
                    'error': f'Directory not found: {bluemap_path}'
                }
            
            logger.info("✅ Папка найдена, получаю размер...")
            
            # Используем более быструю команду с --max-depth
            cmd_size = f"du -sm --max-depth=0 {bluemap_path} 2>/dev/null | cut -f1"
            result_size = await client.execute(cmd_size, timeout=30)
            size_mb = int(result_size.strip()) if result_size.strip() else 0
            
            logger.info(f"💾 Размер получен: {size_mb} MB")
            
            # Человеко-читаемый формат
            cmd_human = f"du -sh --max-depth=0 {bluemap_path} 2>/dev/null | cut -f1"
            result_human = await client.execute(cmd_human, timeout=30)
            size_human = result_human.strip() or f"{size_mb}M"
            
            logger.info(f"📊 Форматированный размер: {size_human}")
            
            # Подсчет файлов - с ограничением глубины для скорости
            cmd_files = f"find {bluemap_path}/web/maps/ -maxdepth 3 -type f 2>/dev/null | wc -l"
            result_files = await client.execute(cmd_files, timeout=20)
            file_count = int(result_files.strip()) if result_files.strip() else 0
            
            logger.info(f"🗂️ Файлов найдено: {file_count}")
            
            return {
                'size_mb': size_mb,
                'size_human': size_human,
                'file_count': file_count,
                'path': bluemap_path
            }
        except asyncio.TimeoutError:
            logger.error("⏱️ Timeout при получении размера карты")
            return {
                'size_mb': 0,
                'size_human': 'Unknown',
                'file_count': 0,
                'path': bluemap_path,
                'error': 'Timeout: карта слишком большая для быстрого подсчета'
            }
        except Exception as e:
            logger.error(f"❌ Error getting BlueMap size: {e}", exc_info=True)
            return {
                'size_mb': 0,
                'size_human': 'Unknown',
                'file_count': 0,
                'path': bluemap_path,
                'error': str(e)
            }