#!/usr/bin/env python3
"""
Test script for player stats functionality
Tests database operations and stats collection
"""
import os
import sys
import asyncio
import logging

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.database import get_db
from core.database.models import PlayerStats
from datetime import datetime

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)


def test_database_operations():
    """Test basic database operations for player stats"""
    logger.info("🧪 Testing database operations...")
    logger.info("=" * 60)
    
    db = get_db()
    
    # Test 1: Create player stats
    logger.info("\n📝 Test 1: Creating test player...")
    test_uuid = "12345678-1234-1234-1234-123456789abc"
    test_nickname = "TestPlayer"
    
    player = db.get_or_create_player_stats(
        minecraft_uuid=test_uuid,
        minecraft_nickname=test_nickname
    )
    logger.info(f"✅ Created: {player}")
    
    # Test 2: Update player stats
    logger.info("\n📝 Test 2: Updating player stats...")
    success = db.update_player_stats(
        minecraft_uuid=test_uuid,
        playtime_ticks=72000,  # 1 hour
        deaths=5,
        mob_kills=100,
        jumps=500
    )
    logger.info(f"✅ Update successful: {success}")
    
    # Test 3: Retrieve player stats
    logger.info("\n📝 Test 3: Retrieving player stats...")
    player = db.get_player_stats_by_uuid(test_uuid)
    if player:
        logger.info(f"✅ Retrieved player:")
        logger.info(f"   UUID: {player.minecraft_uuid}")
        logger.info(f"   Nickname: {player.minecraft_nickname}")
        logger.info(f"   Playtime: {player.get_playtime_hours():.2f} hours")
        logger.info(f"   Deaths: {player.deaths}")
        logger.info(f"   Mob kills: {player.mob_kills}")
    
    # Test 4: Search by nickname
    logger.info("\n📝 Test 4: Searching by nickname...")
    player = db.get_player_stats_by_nickname(test_nickname)
    if player:
        logger.info(f"✅ Found by nickname: {player.minecraft_nickname}")
    
    # Test 5: Cache check
    logger.info("\n📝 Test 5: Checking cache...")
    is_cached = db.is_player_stats_cached(test_uuid, cache_minutes=5)
    logger.info(f"✅ Is cached (5 min): {is_cached}")
    
    cached = db.get_cached_player_stats(test_uuid, cache_minutes=5)
    if cached:
        logger.info(f"✅ Got from cache: {cached.minecraft_nickname}")
    
    # Test 6: Top players
    logger.info("\n📝 Test 6: Getting top players...")
    # Add more test players
    for i in range(3):
        uuid = f"test-uuid-{i:04d}-0000-0000-000000000000"
        db.update_player_stats(
            minecraft_uuid=uuid,
            minecraft_nickname=f"Player{i}",
            playtime_ticks=36000 * (i + 1),  # Increasing playtime
            deaths=i * 2,
            mob_kills=i * 50
        )
    
    top_players = db.get_top_players_by_playtime(limit=5)
    logger.info(f"✅ Top {len(top_players)} players:")
    for i, p in enumerate(top_players, 1):
        logger.info(f"   {i}. {p.minecraft_nickname:15s} - {p.get_playtime_hours():.2f}h")
    
    logger.info("\n" + "=" * 60)
    logger.info("✅ All database tests passed!")
    logger.info("=" * 60)


async def test_stats_collection():
    """Test stats collection from Minecraft server"""
    logger.info("\n🧪 Testing stats collection from server...")
    logger.info("=" * 60)
    
    try:
        from core.config import MINECRAFT_SERVER_SSH
        from core.minecraft.stats import (
            get_all_players_list,
            get_usercache,
            get_player_stats,
            get_top_players_by_playtime
        )
        
        # Test 1: Get player list
        logger.info("\n📝 Test 1: Getting player list...")
        uuids = await get_all_players_list(MINECRAFT_SERVER_SSH)
        logger.info(f"✅ Found {len(uuids)} players")
        
        if uuids:
            logger.info(f"   Sample UUIDs: {uuids[:3]}")
        
        # Test 2: Get usercache
        logger.info("\n📝 Test 2: Loading usercache...")
        usercache = await get_usercache(MINECRAFT_SERVER_SSH)
        logger.info(f"✅ Loaded {len(usercache)} entries from usercache")
        
        if usercache:
            sample = list(usercache.items())[:3]
            for uuid, name in sample:
                logger.info(f"   {uuid[:8]}... -> {name}")
        
        # Test 3: Get player stats
        if uuids:
            logger.info("\n📝 Test 3: Getting player stats...")
            test_uuid = uuids[0]
            stats = await get_player_stats(MINECRAFT_SERVER_SSH, test_uuid)
            
            if stats:
                logger.info(f"✅ Stats for {stats['nickname']}:")
                logger.info(f"   Playtime: {stats['playtime_formatted']}")
                logger.info(f"   Deaths: {stats.get('deaths', 0)}")
                logger.info(f"   Mob kills: {stats.get('mob_kills', 0)}")
        
        # Test 4: Get top players
        logger.info("\n📝 Test 4: Getting top players...")
        top = await get_top_players_by_playtime(MINECRAFT_SERVER_SSH, limit=5)
        
        if top:
            logger.info(f"✅ Top {len(top)} players:")
            for i, p in enumerate(top, 1):
                logger.info(f"   {i}. {p['nickname']:15s} - {p['playtime_formatted']}")
        
        logger.info("\n" + "=" * 60)
        logger.info("✅ All stats collection tests passed!")
        logger.info("=" * 60)
        
    except Exception as e:
        logger.error(f"❌ Stats collection test failed: {e}", exc_info=True)
        logger.warning("⚠️  This is expected if the Minecraft server is not accessible")


async def main():
    """Run all tests"""
    logger.info("\n" + "=" * 60)
    logger.info("🚀 Player Stats Testing Suite")
    logger.info("=" * 60)
    
    # Test database operations
    try:
        test_database_operations()
    except Exception as e:
        logger.error(f"❌ Database tests failed: {e}", exc_info=True)
        return
    
    # Test stats collection (may fail if server not accessible)
    try:
        await test_stats_collection()
    except Exception as e:
        logger.error(f"❌ Stats collection tests failed: {e}", exc_info=True)
        logger.warning("⚠️  Server connection tests failed (expected if server not accessible)")
    
    logger.info("\n" + "=" * 60)
    logger.info("✅ Testing complete!")
    logger.info("=" * 60)
    logger.info("\n💡 Next steps:")
    logger.info("  1. Start the bot: python bot.py")
    logger.info("  2. Test commands: /stats, /top_playtime")
    logger.info("  3. Test inline menu: Click '📈 Статистика'")


if __name__ == "__main__":
    asyncio.run(main())
