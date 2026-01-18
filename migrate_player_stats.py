#!/usr/bin/env python3
"""
Migration script to add player_stats table to the database

This migration adds support for tracking Minecraft player statistics
including playtime, deaths, mob kills, and other metrics.
"""
import os
import sys
import logging
from datetime import datetime

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.database import get_db
from core.database.models import Base, PlayerStats

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)


def migrate_player_stats():
    """Create player_stats table if it doesn't exist"""
    logger.info("🚀 Starting player_stats table migration...")
    logger.info("=" * 60)
    
    try:
        db = get_db()
        
        # Check if table already exists
        from sqlalchemy import inspect
        inspector = inspect(db.engine)
        existing_tables = inspector.get_table_names()
        
        if 'player_stats' in existing_tables:
            logger.info("ℹ️  Table 'player_stats' already exists")
            
            # Check columns
            columns = [col['name'] for col in inspector.get_columns('player_stats')]
            logger.info(f"📋 Existing columns: {', '.join(columns)}")
            
            # Add new columns if they don't exist (for future migrations)
            # This is a safety check for any additional columns we might add
            expected_columns = {
                'id', 'minecraft_uuid', 'minecraft_nickname', 
                'playtime_ticks', 'deaths', 'mob_kills', 'jumps',
                'last_updated', 'first_seen', 'last_seen'
            }
            
            missing_columns = expected_columns - set(columns)
            if missing_columns:
                logger.warning(f"⚠️  Missing columns: {', '.join(missing_columns)}")
                logger.warning("⚠️  You may need to manually add these columns or drop the table")
            else:
                logger.info("✅ All expected columns are present")
        else:
            # Create the table
            logger.info("📝 Creating 'player_stats' table...")
            Base.metadata.tables['player_stats'].create(db.engine)
            logger.info("✅ Table 'player_stats' created successfully")
        
        # Display table structure
        logger.info("\n" + "=" * 60)
        logger.info("📊 player_stats table structure:")
        logger.info("=" * 60)
        
        inspector = inspect(db.engine)
        columns = inspector.get_columns('player_stats')
        
        for col in columns:
            col_type = str(col['type'])
            nullable = "NULL" if col['nullable'] else "NOT NULL"
            logger.info(f"  • {col['name']:20s} {col_type:15s} {nullable}")
        
        # Display indexes
        indexes = inspector.get_indexes('player_stats')
        if indexes:
            logger.info("\n🔍 Indexes:")
            for idx in indexes:
                cols = ', '.join(idx['column_names'])
                unique = "UNIQUE" if idx['unique'] else ""
                logger.info(f"  • {idx['name']:30s} ({cols}) {unique}")
        
        logger.info("\n" + "=" * 60)
        logger.info("✅ Migration completed successfully!")
        logger.info("=" * 60)
        
        logger.info("\n💡 Next steps:")
        logger.info("  1. Start the bot with: python bot.py")
        logger.info("  2. Use /stats command to view player statistics")
        logger.info("  3. Use /top_playtime to see top players")
        logger.info("  4. Click '📈 Статистика' button in the main menu")
        
    except Exception as e:
        logger.error(f"❌ Migration failed: {e}", exc_info=True)
        sys.exit(1)


def check_migration_status():
    """Check if migration is needed"""
    logger.info("🔍 Checking migration status...")
    
    try:
        db = get_db()
        from sqlalchemy import inspect
        inspector = inspect(db.engine)
        existing_tables = inspector.get_table_names()
        
        logger.info(f"\n📋 Existing tables ({len(existing_tables)}):")
        for table in existing_tables:
            logger.info(f"  • {table}")
        
        if 'player_stats' in existing_tables:
            logger.info("\n✅ player_stats table exists")
            
            # Count records
            from sqlalchemy import text
            with db.engine.connect() as conn:
                result = conn.execute(text("SELECT COUNT(*) FROM player_stats"))
                count = result.scalar()
                logger.info(f"📊 Total player records: {count}")
            
            return True
        else:
            logger.info("\n⚠️  player_stats table does NOT exist")
            logger.info("💡 Run migration to create it")
            return False
            
    except Exception as e:
        logger.error(f"❌ Error checking migration status: {e}")
        return False


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description='Player stats table migration')
    parser.add_argument(
        '--check',
        action='store_true',
        help='Check migration status without applying changes'
    )
    
    args = parser.parse_args()
    
    if args.check:
        check_migration_status()
    else:
        migrate_player_stats()
