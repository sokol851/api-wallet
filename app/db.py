from decouple import config
from sqlalchemy import create_engine, text
from sqlalchemy.ext.asyncio import (AsyncSession, async_sessionmaker,
                                    create_async_engine)
from sqlalchemy.orm import declarative_base

user = config('POSTGRES_USER')
password = config('POSTGRES_PASSWORD')
host = config('POSTGRES_HOST')
port = config('POSTGRES_PORT')
dbname = config('POSTGRES_DB')

# Создаем движок для подключения без указания базы данных
default_engine = create_engine(f"postgresql://{user}:{password}@{host}:{port}/postgres")

# Создаем базу данных, если она не существует
with default_engine.connect() as conn:
    conn = conn.execution_options(isolation_level="AUTOCOMMIT")
    # Проверяем, существует ли база данных
    result = conn.execute(text(f"SELECT 1 FROM pg_database WHERE datname = '{dbname}'"))
    exists = result.scalar() is not None
    # Создаем базу данных, если она не существует
    if not exists:
        conn.execute(text(f"CREATE DATABASE {dbname}"))

DATABASE_URL = f"postgresql+asyncpg://{user}:{password}@{host}:{port}/{dbname}"

engine = create_async_engine(DATABASE_URL, echo=True)

async_session = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)

Base = declarative_base()
