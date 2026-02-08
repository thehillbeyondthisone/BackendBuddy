from sqlalchemy import create_engine, Column, Integer, String, Boolean, DateTime
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from datetime import datetime
import os
import logging
import traceback

# Set up logging
logger = logging.getLogger("BackendBuddy.Database")

# Database setup
DB_PATH = os.path.join(os.path.dirname(__file__), "vibecoding.db")
DATABASE_URL = f"sqlite:///{DB_PATH}"
logger.info(f"Database path: {DB_PATH}")

engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


class ProjectConfig(Base):
    """Single project configuration"""
    __tablename__ = "project_config"
    
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, default="My Project")
    directory = Column(String, nullable=True)
    command = Column(String, nullable=True)
    frontend_directory = Column(String, nullable=True)
    frontend_command = Column(String, nullable=True)
    port = Column(Integer, nullable=True)
    lan_ip = Column(String, nullable=True)
    lan_enabled = Column(Boolean, default=False)
    ngrok_enabled = Column(Boolean, default=False)
    cloudflare_enabled = Column(Boolean, default=False)
    queue_enabled = Column(Boolean, default=True)
    max_concurrent_users = Column(Integer, default=1)
    prioritize_localhost = Column(Boolean, default=True)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class QueueEntry(Base):
    """Queue management for remote users"""
    __tablename__ = "queue_entries"
    
    id = Column(Integer, primary_key=True, index=True)
    session_id = Column(String, unique=True, index=True)
    is_active = Column(Boolean, default=False)
    joined_at = Column(DateTime, default=datetime.utcnow)
    last_heartbeat = Column(DateTime, default=datetime.utcnow)
    position = Column(Integer, nullable=True)


class ProjectPreset(Base):
    """Saved project presets for quick loading"""
    __tablename__ = "project_presets"
    
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, unique=True, index=True)
    directory = Column(String, nullable=True)
    command = Column(String, nullable=True)
    frontend_directory = Column(String, nullable=True)
    frontend_command = Column(String, nullable=True)
    port = Column(Integer, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)


def init_db():
    """Initialize database and create default config if needed"""
    logger.info("Initializing database...")
    try:
        Base.metadata.create_all(bind=engine)
        logger.debug("Database tables created")
        
        # Migration: Check if cloudflare_enabled exists, if not add it
        try:
            from sqlalchemy import inspect, text
            inspector = inspect(engine)
            columns = [c['name'] for c in inspector.get_columns('project_config')]
            if 'cloudflare_enabled' not in columns:
                logger.info("Migrating database: adding cloudflare_enabled column")
                with engine.connect() as conn:
                    conn.execute(text("ALTER TABLE project_config ADD COLUMN cloudflare_enabled BOOLEAN DEFAULT 0"))
                    conn.commit()
            
            if 'frontend_directory' not in columns:
                logger.info("Migrating database: adding frontend_directory column")
                with engine.connect() as conn:
                    conn.execute(text("ALTER TABLE project_config ADD COLUMN frontend_directory VARCHAR"))
                    conn.execute(text("ALTER TABLE project_config ADD COLUMN frontend_command VARCHAR"))
                    conn.commit()

            # Migration for waiting room settings
            if 'max_concurrent_users' not in columns:
                logger.info("Migrating database: adding max_concurrent_users column")
                with engine.connect() as conn:
                    conn.execute(text("ALTER TABLE project_config ADD COLUMN max_concurrent_users INTEGER DEFAULT 1"))
                    conn.commit()
            
            if 'prioritize_localhost' not in columns:
                logger.info("Migrating database: adding prioritize_localhost column")
                with engine.connect() as conn:
                    conn.execute(text("ALTER TABLE project_config ADD COLUMN prioritize_localhost BOOLEAN DEFAULT 1"))
                    conn.commit()

            logger.info("Migration check complete")
        except Exception as e:
            logger.error(f"Migration failed: {e}")

        # Create default project config if none exists
        db = SessionLocal()
        try:
            config = db.query(ProjectConfig).first()
            if not config:
                logger.info("No config found, creating default configuration")
                config = ProjectConfig(
                    name="My Project",
                    directory="",
                    command="",
                    frontend_directory="",
                    frontend_command="",
                    port=8000,
                    lan_ip="",
                    lan_enabled=False,
                    ngrok_enabled=False,
                    cloudflare_enabled=False,
                    queue_enabled=True,
                    max_concurrent_users=1,
                    prioritize_localhost=True
                )
                db.add(config)
                db.commit()
                logger.info("Default configuration created")
            else:
                logger.debug(f"Existing config found: name={config.name}, port={config.port}")
        except Exception as e:
            logger.error(f"Error checking/creating default config: {e}")
            logger.error(traceback.format_exc())
            raise
        finally:
            db.close()
            
        logger.info("Database initialization complete")
    except Exception as e:
        logger.error(f"Database initialization failed: {e}")
        logger.error(traceback.format_exc())
        raise


def get_db():
    """Dependency for FastAPI routes"""
    db = SessionLocal()
    try:
        yield db
    except Exception as e:
        logger.error(f"Database session error: {e}")
        logger.error(traceback.format_exc())
        raise
    finally:
        db.close()
