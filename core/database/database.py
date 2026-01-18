"""Database management"""
import logging
from typing import Optional, List
from datetime import datetime, timedelta
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from .models import Base, User, UserRole, Group, PlayerStats

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

    def get_or_create_group(
        self,
        telegram_id: int,
        title: Optional[str] = None,
        username: Optional[str] = None,
        chat_type: Optional[str] = None
    ) -> Group:
        """Get or create group by telegram ID"""
        session = self.get_session()
        try:
            group = session.query(Group).filter(Group.telegram_id == telegram_id).first()

            if group:
                # Update group info if changed
                updated = False
                if title and group.title != title:
                    group.title = title
                    updated = True
                if username and group.username != username:
                    group.username = username
                    updated = True
                if chat_type and group.type != chat_type:
                    group.type = chat_type
                    updated = True

                if updated:
                    session.commit()
                    session.refresh(group)
                    logger.info(f"📝 Updated group {telegram_id}")

                return group

            # Create new group
            group = Group(
                telegram_id=telegram_id,
                title=title,
                username=username,
                type=chat_type
            )
            session.add(group)
            session.commit()
            session.refresh(group)
            logger.info(f"✅ Created new group {telegram_id}: {title}")
            return group

        finally:
            session.close()

    def get_group_by_telegram_id(self, telegram_id: int) -> Optional[Group]:
        """Get group by telegram ID"""
        session = self.get_session()
        try:
            return session.query(Group).filter(Group.telegram_id == telegram_id).first()
        finally:
            session.close()

    def is_group_commands_enabled(self, telegram_id: int) -> bool:
        """Check if commands are enabled for group"""
        group = self.get_group_by_telegram_id(telegram_id)
        return group.commands_enabled if group else True  # Default: enabled

    def set_group_commands_enabled(self, telegram_id: int, enabled: bool) -> bool:
        """Enable/disable commands for group"""
        session = self.get_session()
        try:
            group = session.query(Group).filter(Group.telegram_id == telegram_id).first()
            if group:
                group.commands_enabled = enabled
                session.commit()
                logger.info(f"✅ Commands {'enabled' if enabled else 'disabled'} for group {telegram_id}")
                return True
            return False
        finally:
            session.close()

    def get_all_groups(self) -> List[Group]:
        """Get all groups"""
        session = self.get_session()
        try:
            return session.query(Group).all()
        finally:
            session.close()

    # ==================== PLAYER STATS METHODS ====================

    def get_or_create_player_stats(
        self,
        minecraft_uuid: str,
        minecraft_nickname: Optional[str] = None
    ) -> PlayerStats:
        """Get or create player stats by Minecraft UUID"""
        session = self.get_session()
        try:
            player = session.query(PlayerStats).filter(
                PlayerStats.minecraft_uuid == minecraft_uuid
            ).first()

            if player:
                # Update nickname if provided and different
                if minecraft_nickname and player.minecraft_nickname != minecraft_nickname:
                    player.minecraft_nickname = minecraft_nickname
                    session.commit()
                    session.refresh(player)
                    logger.info(f"📝 Updated nickname for {minecraft_uuid}: {minecraft_nickname}")
                return player

            # Create new player stats
            player = PlayerStats(
                minecraft_uuid=minecraft_uuid,
                minecraft_nickname=minecraft_nickname,
                first_seen=datetime.utcnow()
            )
            session.add(player)
            session.commit()
            session.refresh(player)
            logger.info(f"✅ Created player stats for {minecraft_uuid} ({minecraft_nickname})")
            return player

        finally:
            session.close()

    def update_player_stats(
        self,
        minecraft_uuid: str,
        playtime_ticks: Optional[int] = None,
        deaths: Optional[int] = None,
        mob_kills: Optional[int] = None,
        jumps: Optional[int] = None,
        blocks_mined: Optional[int] = None,
        damage_dealt: Optional[int] = None,
        damage_taken: Optional[int] = None,
        minecraft_nickname: Optional[str] = None,
        last_seen: Optional[datetime] = None
    ) -> bool:
        """Update player statistics"""
        session = self.get_session()
        try:
            player = session.query(PlayerStats).filter(
                PlayerStats.minecraft_uuid == minecraft_uuid
            ).first()

            if not player:
                # Create if doesn't exist
                player = PlayerStats(
                    minecraft_uuid=minecraft_uuid,
                    minecraft_nickname=minecraft_nickname,
                    first_seen=datetime.utcnow()
                )
                session.add(player)

            # Update fields
            if playtime_ticks is not None:
                player.playtime_ticks = playtime_ticks
            if deaths is not None:
                player.deaths = deaths
            if mob_kills is not None:
                player.mob_kills = mob_kills
            if jumps is not None:
                player.jumps = jumps
            if blocks_mined is not None:
                player.blocks_mined = blocks_mined
            if damage_dealt is not None:
                player.damage_dealt = damage_dealt
            if damage_taken is not None:
                player.damage_taken = damage_taken
            if minecraft_nickname is not None:
                player.minecraft_nickname = minecraft_nickname
            if last_seen is not None:
                player.last_seen = last_seen

            player.last_updated = datetime.utcnow()

            session.commit()
            logger.info(f"✅ Updated stats for {minecraft_uuid}")
            return True

        except Exception as e:
            logger.error(f"❌ Error updating player stats: {e}")
            session.rollback()
            return False
        finally:
            session.close()

    def get_player_stats_by_uuid(self, minecraft_uuid: str) -> Optional[PlayerStats]:
        """Get player stats by Minecraft UUID"""
        session = self.get_session()
        try:
            return session.query(PlayerStats).filter(
                PlayerStats.minecraft_uuid == minecraft_uuid
            ).first()
        finally:
            session.close()

    def get_player_stats_by_nickname(self, minecraft_nickname: str) -> Optional[PlayerStats]:
        """Get player stats by Minecraft nickname (case-insensitive)"""
        session = self.get_session()
        try:
            return session.query(PlayerStats).filter(
                PlayerStats.minecraft_nickname.ilike(minecraft_nickname)
            ).first()
        finally:
            session.close()

    def get_all_player_stats(self, limit: Optional[int] = None) -> List[PlayerStats]:
        """Get all player stats"""
        session = self.get_session()
        try:
            query = session.query(PlayerStats)
            if limit:
                query = query.limit(limit)
            return query.all()
        finally:
            session.close()

    def get_top_players_by_playtime(self, limit: int = 10) -> List[PlayerStats]:
        """Get top players by playtime"""
        session = self.get_session()
        try:
            return session.query(PlayerStats).order_by(
                PlayerStats.playtime_ticks.desc()
            ).limit(limit).all()
        finally:
            session.close()

    def is_player_stats_cached(self, minecraft_uuid: str, cache_minutes: int = 5) -> bool:
        """Check if player stats are cached (updated recently)"""
        player = self.get_player_stats_by_uuid(minecraft_uuid)
        if not player:
            return False

        time_since_update = datetime.utcnow() - player.last_updated
        return time_since_update < timedelta(minutes=cache_minutes)

    def get_cached_player_stats(
        self,
        minecraft_uuid: str,
        cache_minutes: int = 5
    ) -> Optional[PlayerStats]:
        """Get cached player stats if fresh enough"""
        if self.is_player_stats_cached(minecraft_uuid, cache_minutes):
            return self.get_player_stats_by_uuid(minecraft_uuid)
        return None

    def get_cached_player_stats_by_nickname(
        self,
        minecraft_nickname: str,
        cache_minutes: int = 5
    ) -> Optional[PlayerStats]:
        """Get cached player stats by nickname if fresh enough"""
        player = self.get_player_stats_by_nickname(minecraft_nickname)
        if not player:
            return None
        
        time_since_update = datetime.utcnow() - player.last_updated
        if time_since_update < timedelta(minutes=cache_minutes):
            return player
        return None


# Global database instance
_db: Optional[Database] = None


def get_db() -> Database:
    """Get global database instance"""
    global _db
    if _db is None:
        _db = Database()
        _db.init_db()
    return _db
