import os
from pathlib import Path
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase
from config import get_settings


class Base(DeclarativeBase):
    pass


def get_engine():
    settings = get_settings()
    # Ensure the directory exists for SQLite file
    db_url = settings.database_url
    if "sqlite" in db_url:
        db_path = db_url.split("///")[-1]
        if db_path:
            Path(db_path).parent.mkdir(parents=True, exist_ok=True)
    return create_async_engine(
        db_url,
        echo=False,
        connect_args={"check_same_thread": False},
    )


engine = get_engine()
AsyncSessionLocal = async_sessionmaker(engine, expire_on_commit=False)


async def get_db() -> AsyncSession:
    async with AsyncSessionLocal() as session:
        try:
            yield session
        finally:
            await session.close()
