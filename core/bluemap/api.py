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
