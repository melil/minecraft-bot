#!/usr/bin/env python3
"""Migration script to migrate admin IDs from text file to database"""
import os
import sys
import logging

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.database import get_db, User, UserRole

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Admin IDs to migrate
ADMIN_IDS = [
    138349349,
    140821964,
    451548653,
    78120051,  # This will be super admin
    851242077,
    505878676,
    860938417,
]

SUPER_ADMIN_ID = 78120051  # ID пользователя с супер админом


def migrate_admins():
    """Migrate admin IDs to database"""
    logger.info("🚀 Starting admin migration...")
    
    db = get_db()
    
    # Create super admin
    logger.info(f"Creating super admin with ID {SUPER_ADMIN_ID}")
    super_admin = db.get_or_create_user(
        telegram_id=SUPER_ADMIN_ID,
        auto_promote_ids=[]
    )
    if super_admin.role != UserRole.SUPER_ADMIN:
        db.update_user_role(SUPER_ADMIN_ID, UserRole.SUPER_ADMIN)
        logger.info(f"✅ Promoted user {SUPER_ADMIN_ID} to SUPER_ADMIN")
    
    # Create admins
    for admin_id in ADMIN_IDS:
        if admin_id == SUPER_ADMIN_ID:
            continue  # Skip super admin
        
        logger.info(f"Creating admin with ID {admin_id}")
        admin = db.get_or_create_user(
            telegram_id=admin_id,
            auto_promote_ids=[]
        )
        if admin.role == UserRole.USER:
            db.update_user_role(admin_id, UserRole.ADMIN)
            logger.info(f"✅ Promoted user {admin_id} to ADMIN")
    
    # Display results
    logger.info("\n" + "=" * 50)
    logger.info("📊 Migration complete!")
    logger.info("=" * 50)
    
    all_admins = db.get_all_admins()
    logger.info(f"\nTotal admins: {len(all_admins)}")
    
    for user in all_admins:
        role_emoji = "👑" if user.is_super_admin() else "🔑"
        logger.info(f"{role_emoji} {user.telegram_id} - {user.role.value}")
    
    logger.info("\n✅ Migration successful!")


if __name__ == "__main__":
    migrate_admins()
