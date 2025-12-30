"""Database management using SQLAlchemy"""

import os
from pathlib import Path
from typing import Optional
from sqlalchemy import create_engine, Column, String, DateTime, Text, Boolean, Integer
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, Session
from loguru import logger

Base = declarative_base()


class ClipboardEntryDB(Base):
    """Database model for clipboard entries"""
    __tablename__ = 'clipboard_entries'

    id = Column(Integer, primary_key=True, autoincrement=True)
    content_hash = Column(String(64), unique=True, nullable=False, index=True)
    encrypted_content = Column(Text, nullable=False)
    encrypted_nonce = Column(String(255), nullable=False)
    encrypted_tag = Column(String(255), nullable=False)
    timestamp = Column(DateTime, nullable=False, index=True)
    category = Column(String(50), nullable=False)
    is_favorite = Column(Boolean, default=False)
    entry_metadata = Column(Text)  # JSON string - renamed from 'metadata' to avoid SQLAlchemy reserved word


class SettingsDB(Base):
    """Database model for application settings"""
    __tablename__ = 'settings'

    key = Column(String(100), primary_key=True)
    value = Column(Text)
    updated_at = Column(DateTime)


class DatabaseManager:
    """Manages database connections and operations"""

    def __init__(self, db_path: Optional[str] = None):
        """
        Initialize database manager

        Args:
            db_path: Path to database file (defaults to app data directory)
        """
        if db_path is None:
            # Use default app data directory
            app_data = Path(os.environ.get('APPDATA', '.')) / 'ClipboardHistory'
            app_data.mkdir(exist_ok=True)
            db_path = str(app_data / 'clipboard.db')

        self.db_path = db_path
        self.engine = None
        self.SessionLocal = None

        self._initialize_database()

    def _initialize_database(self):
        """Initialize database connection and create tables"""
        try:
            # Create SQLite database
            self.engine = create_engine(
                f'sqlite:///{self.db_path}',
                connect_args={'check_same_thread': False}
            )

            # Create tables if they don't exist
            Base.metadata.create_all(bind=self.engine)

            # Create session factory
            self.SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=self.engine)

            logger.info(f"Database initialized at: {self.db_path}")

        except Exception as e:
            logger.error(f"Failed to initialize database: {e}")
            raise

    def get_session(self) -> Session:
        """
        Get database session

        Returns:
            SQLAlchemy session
        """
        if self.SessionLocal is None:
            raise RuntimeError("Database not initialized")

        return self.SessionLocal()

    def close(self):
        """Close database connection"""
        if self.engine:
            self.engine.dispose()
            logger.info("Database connection closed")

    def backup(self, backup_path: str):
        """
        Create database backup

        Args:
            backup_path: Path for backup file
        """
        try:
            import shutil
            shutil.copy2(self.db_path, backup_path)
            logger.info(f"Database backed up to: {backup_path}")

        except Exception as e:
            logger.error(f"Backup failed: {e}")
            raise

    def vacuum(self):
        """Optimize database (VACUUM operation)"""
        try:
            from sqlalchemy import text
            with self.engine.connect() as conn:
                conn.execute(text("VACUUM"))
                conn.commit()
            logger.info("Database optimized (VACUUM completed)")

        except Exception as e:
            logger.error(f"VACUUM failed: {e}")
            raise

    def get_size(self) -> int:
        """
        Get database file size in bytes

        Returns:
            Size in bytes
        """
        if os.path.exists(self.db_path):
            return os.path.getsize(self.db_path)
        return 0

    def reset(self):
        """Reset database (drop all tables and recreate)"""
        try:
            Base.metadata.drop_all(bind=self.engine)
            Base.metadata.create_all(bind=self.engine)
            logger.info("Database reset completed")

        except Exception as e:
            logger.error(f"Database reset failed: {e}")
            raise