"""
Database engine and initialization.
Phase 1: SQLite with SQLAlchemy (async).
Migrations via Alembic (set up in later phase).
"""

from pathlib import Path

from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase

from app.logging.logger import get_logger

logger = get_logger(__name__)

# Database file location
DB_DIR = Path.home() / ".ai-teleprompter"
DB_PATH = DB_DIR / "teleprompter.db"


class Base(DeclarativeBase):
    """Base class for all ORM models."""
    pass


# Async engine — SQLite
engine = create_async_engine(
    f"sqlite+aiosqlite:///{DB_PATH}",
    echo=False,
    connect_args={"check_same_thread": False},
)

# Session factory
AsyncSessionLocal = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


async def init_db() -> None:
    """Initialize the database, creating tables if needed."""
    DB_DIR.mkdir(parents=True, exist_ok=True)
    logger.info("Database path", path=str(DB_PATH))

    async with engine.begin() as conn:
        # Phase 1: Create all tables directly.
        # Phase 2+: Replace with Alembic migrations.
        await conn.run_sync(Base.metadata.create_all)

    logger.info("Database ready")


async def get_session() -> AsyncSession:
    """Dependency: get a database session."""
    async with AsyncSessionLocal() as session:
        yield session
