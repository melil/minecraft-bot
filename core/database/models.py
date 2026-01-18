"""Database models for user management"""
from datetime import datetime
from enum import Enum
from sqlalchemy import Column, Integer, String, DateTime, Enum as SQLEnum, BigInteger, Boolean, Float
from sqlalchemy.ext.declarative import declarative_base

Base = declarative_base()


class UserRole(str, Enum):
    """User roles enum"""
    USER = "user"
    ADMIN = "admin"
    SUPER_ADMIN = "super_admin"


class User(Base):
    """User model"""
    __tablename__ = 'users'

    id = Column(Integer, primary_key=True)
    telegram_id = Column(BigInteger, unique=True, nullable=False, index=True)
    username = Column(String(255), nullable=True)  # Telegram username
    first_name = Column(String(255), nullable=True)
    last_name = Column(String(255), nullable=True)
    minecraft_nickname = Column(String(255), nullable=True)
    telegram_link = Column(String(512), nullable=True)  # t.me/username или полная ссылка
    role = Column(SQLEnum(UserRole), nullable=False, default=UserRole.USER)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)

    def __repr__(self):
        return f"<User(telegram_id={self.telegram_id}, username={self.username}, role={self.role})>"

    def is_admin(self) -> bool:
        """Check if user is admin or super admin"""
        return self.role in [UserRole.ADMIN, UserRole.SUPER_ADMIN]

    def is_super_admin(self) -> bool:
        """Check if user is super admin"""
        return self.role == UserRole.SUPER_ADMIN

    def get_display_name(self) -> str:
        """Get user display name"""
        if self.username:
            return f"@{self.username}"
        if self.first_name and self.last_name:
            return f"{self.first_name} {self.last_name}"
        if self.first_name:
            return self.first_name
        return f"User {self.telegram_id}"

    def get_telegram_link(self) -> str:
        """Get telegram link for user"""
        if self.telegram_link:
            return self.telegram_link
        if self.username:
            return f"https://t.me/{self.username}"
        return f"tg://user?id={self.telegram_id}"


class Group(Base):
    """Group/Chat model"""
    __tablename__ = 'groups'

    id = Column(Integer, primary_key=True)
    telegram_id = Column(BigInteger, unique=True, nullable=False, index=True)
    title = Column(String(255), nullable=True)
    username = Column(String(255), nullable=True)  # Group username if exists
    type = Column(String(50), nullable=True)  # group, supergroup, channel
    is_active = Column(Boolean, default=True)
    commands_enabled = Column(Boolean, default=True)  # Allow commands in this group
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)

    def __repr__(self):
        return f"<Group(telegram_id={self.telegram_id}, title={self.title})>"

    def get_display_name(self) -> str:
        """Get group display name"""
        if self.title:
            return self.title
        if self.username:
            return f"@{self.username}"
        return f"Group {self.telegram_id}"


class PlayerStats(Base):
    """Player statistics from Minecraft"""
    __tablename__ = 'player_stats'

    id = Column(Integer, primary_key=True)
    minecraft_uuid = Column(String(36), unique=True, nullable=False, index=True)
    minecraft_nickname = Column(String(16), nullable=True, index=True)
    playtime_ticks = Column(BigInteger, default=0)  # В тиках (20 тиков = 1 секунда)
    deaths = Column(Integer, default=0)
    mob_kills = Column(Integer, default=0)
    jumps = Column(Integer, default=0)
    last_updated = Column(DateTime, nullable=False, default=datetime.utcnow)
    first_seen = Column(DateTime, nullable=False, default=datetime.utcnow)
    last_seen = Column(DateTime, nullable=True)

    def __repr__(self):
        return f"<PlayerStats(uuid={self.minecraft_uuid}, nickname={self.minecraft_nickname}, playtime={self.playtime_ticks})>"

    def get_playtime_hours(self) -> float:
        """Get playtime in hours"""
        return self.playtime_ticks / (20 * 60 * 60)  # 20 ticks/sec * 60 sec/min * 60 min/hour
