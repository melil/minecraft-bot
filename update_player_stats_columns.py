#!/usr/bin/env python3
"""
Migration script to add new columns to player_stats table
Adds: blocks_mined, damage_dealt, damage_taken
"""
import os
import sys
import logging
import sqlite3

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)


def add_columns_to_player_stats():
    """Add new columns to player_stats table"""
    logger.info("🔄 Updating player_stats table with new columns...")
    logger.info("=" * 60)
    
    try:
        # Connect to database
        db_path = "bot.db"
        
        if not os.path.exists(db_path):
            logger.error(f"❌ Database file {db_path} not found!")
            return False
        
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Check existing columns
        cursor.execute("PRAGMA table_info(player_stats)")
        existing_columns = [row[1] for row in cursor.fetchall()]
        
        logger.info(f"📋 Existing columns: {', '.join(existing_columns)}")
        
        # New columns to add
        new_columns = {
            'blocks_mined': 'INTEGER DEFAULT 0',
            'damage_dealt': 'BIGINT DEFAULT 0',
            'damage_taken': 'BIGINT DEFAULT 0'
        }
        
        added_count = 0
        
        for column_name, column_type in new_columns.items():
            if column_name not in existing_columns:
                logger.info(f"➕ Adding column: {column_name} ({column_type})")
                try:
                    cursor.execute(f"ALTER TABLE player_stats ADD COLUMN {column_name} {column_type}")
                    added_count += 1
                    logger.info(f"✅ Column {column_name} added successfully")
                except sqlite3.OperationalError as e:
                    logger.error(f"❌ Failed to add column {column_name}: {e}")
            else:
                logger.info(f"⏭️  Column {column_name} already exists, skipping")
        
        conn.commit()
        conn.close()
        
        logger.info("\n" + "=" * 60)
        if added_count > 0:
            logger.info(f"✅ Successfully added {added_count} new column(s)")
        else:
            logger.info("✅ All columns already exist, no changes needed")
        logger.info("=" * 60)
        
        # Verify
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        cursor.execute("PRAGMA table_info(player_stats)")
        all_columns = cursor.fetchall()
        conn.close()
        
        logger.info("\n📊 Final table structure:")
        for col in all_columns:
            col_id, name, col_type, not_null, default, pk = col
            nullable = "NOT NULL" if not_null else "NULL"
            pk_str = " PRIMARY KEY" if pk else ""
            default_str = f" DEFAULT {default}" if default else ""
            logger.info(f"  • {name:20s} {col_type:15s} {nullable}{default_str}{pk_str}")
        
        return True
        
    except Exception as e:
        logger.error(f"❌ Migration failed: {e}", exc_info=True)
        return False


if __name__ == "__main__":
    logger.info("\n" + "=" * 60)
    logger.info("🚀 Player Stats Table Update")
    logger.info("Adding new columns: blocks_mined, damage_dealt, damage_taken")
    logger.info("=" * 60 + "\n")
    
    success = add_columns_to_player_stats()
    
    if success:
        logger.info("\n💡 Next steps:")
        logger.info("  1. Restart the bot: python bot.py")
        logger.info("  2. Test statistics: Click '📈 Статистика'")
        logger.info("  3. View detailed stats for any player")
        sys.exit(0)
    else:
        logger.error("\n❌ Migration failed! Check errors above.")
        sys.exit(1)
