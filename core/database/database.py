"""Database management"""
import logging
from typing import Optional, List
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from .models import Base, User, UserRole

logger = logging.getLogger(__name__)


class Database:
    """Database manager"""

    def __init__(self, db_url: str = "sqlite:///bot.db"):
        """Initialize database connection"""
        self.engine = create_engine(db_url, echo=False)
        self.SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=self.engine)
        self._initialized = False

    def init_db(self):
        """Create all tables"""
        if not self._initialized:
            Base.metadata.create_all(bind=self.engine)
            self._initialized = True
            logger.info("✅ Database initialized")

    def get_session(self) -> Session:
        """Get database session"""
        return self.SessionLocal()

    def get_or_create_user(
        self,
        telegram_id: int,
        username: Optional[str] = None,
        first_name: Optional[str] = None,
        last_name: Optional[str] = None,
        auto_promote_ids: Optional[List[int]] = None
    ) -> User:
        """
        Get or create user by telegram ID.
        If user exists in auto_promote_ids list and is not admin, promote to admin.
        """
        session = self.get_session()
        try:
            user = session.query(User).filter(User.telegram_id == telegram_id).first()

            if user:
                # Update user info if changed
                updated = False
                if username and user.username != username:
                    user.username = username
                    updated = True
                if first_name and user.first_name != first_name:
                    user.first_name = first_name
                    updated = True
                if last_name and user.last_name != last_name:
                    user.last_name = last_name
                    updated = True

                # Auto-promote to admin if in list and not already admin
                if auto_promote_ids and telegram_id in auto_promote_ids:
                    if user.role == UserRole.USER:
                        user.role = UserRole.ADMIN
                        updated = True
                        logger.info(f"✅ Auto-promoted user {telegram_id} to ADMIN")

                if updated:
                    session.commit()
                    session.refresh(user)
                    logger.info(f"📝 Updated user {telegram_id}")

                return user

            # Create new user
            role = UserRole.USER
            if auto_promote_ids and telegram_id in auto_promote_ids:
                role = UserRole.ADMIN
                logger.info(f"✅ Creating new user {telegram_id} with ADMIN role")

            user = User(
                telegram_id=telegram_id,
                username=username,
                first_name=first_name,
                last_name=last_name,
                role=role
            )
            session.add(user)
            session.commit()
            session.refresh(user)
            logger.info(f"✅ Created new user {telegram_id} with role {role}")
            return user

        finally:
            session.close()

    def get_user_by_telegram_id(self, telegram_id: int) -> Optional[User]:
        """Get user by telegram ID"""
        session = self.get_session()
        try:
            return session.query(User).filter(User.telegram_id == telegram_id).first()
        finally:
            session.close()

    def update_user_minecraft_nickname(self, telegram_id: int, minecraft_nickname: str) -> bool:
        """Update user's Minecraft nickname"""
        session = self.get_session()
        try:
            user = session.query(User).filter(User.telegram_id == telegram_id).first()
            if user:
                user.minecraft_nickname = minecraft_nickname
                session.commit()
                logger.info(f"✅ Updated Minecraft nickname for user {telegram_id}")
                return True
            return False
        finally:
            session.close()

    def update_user_telegram_link(self, telegram_id: int, telegram_link: str) -> bool:
        """Update user's Telegram link"""
        session = self.get_session()
        try:
            user = session.query(User).filter(User.telegram_id == telegram_id).first()
            if user:
                user.telegram_link = telegram_link
                session.commit()
                logger.info(f"✅ Updated Telegram link for user {telegram_id}")
                return True
            return False
        finally:
            session.close()

    def update_user_role(self, telegram_id: int, role: UserRole) -> bool:
        """Update user's role"""
        session = self.get_session()
        try:
            user = session.query(User).filter(User.telegram_id == telegram_id).first()
            if user:
                old_role = user.role
                user.role = role
                session.commit()
                logger.info(f"✅ Updated role for user {telegram_id}: {old_role} -> {role}")
                return True
            return False
        finally:
            session.close()

    def get_all_admins(self) -> List[User]:
        """Get all admin and super admin users"""
        session = self.get_session()
        try:
            return session.query(User).filter(
                User.role.in_([UserRole.ADMIN, UserRole.SUPER_ADMIN])
            ).all()
        finally:
            session.close()

    def get_all_users(self) -> List[User]:
        """Get all users"""
        session = self.get_session()
        try:
            return session.query(User).all()
        finally:
            session.close()

    def is_admin(self, telegram_id: int) -> bool:
        """Check if user is admin or super admin"""
        user = self.get_user_by_telegram_id(telegram_id)
        return user.is_admin() if user else False

    def is_super_admin(self, telegram_id: int) -> bool:
        """Check if user is super admin"""
        user = self.get_user_by_telegram_id(telegram_id)
        return user.is_super_admin() if user else False


# Global database instance
_db: Optional[Database] = None


def get_db() -> Database:
    """Get global database instance"""
    global _db
    if _db is None:
        _db = Database()
        _db.init_db()
    return _db
