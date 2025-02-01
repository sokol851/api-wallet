from contextlib import asynccontextmanager
from uuid import UUID

from fastapi import Depends, FastAPI, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from app.bearer import verify_token
from app.db import Base, async_session, engine
from app.models import Wallet
from app.schemas import WalletResponse


async def get_session() -> AsyncSession:
    """ Создаём сессию """
    async with async_session() as session:
        yield session


@asynccontextmanager
async def lifespan(app: FastAPI):
    """ Управление запуском и завершением """
    # Создаём таблиц при запуске приложения
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield
    # При завершении приложения закрываем соединения
    await engine.dispose()


# Создаём приложение
app = FastAPI(lifespan=lifespan, title='API для взаимодействия с кошельком', version="1.0.0")


@app.get('/api/v1/wallets/{WALLET_UUID}',
         response_model=WalletResponse,
         summary='Получение состояния кошелька по UUID',
         dependencies=[Depends(verify_token)],
         tags=['Работа с кошельком'])
async def get_wallet(wallet_uuid: UUID, db: AsyncSession = Depends(get_session)):
    """ Получение кошелька по UUID """
    # Запрос в базу
    query = select(Wallet).where(Wallet.UUID == wallet_uuid)
    # Ждём результат запроса
    result = await db.execute(query)
    # Забираем единственный результат
    wallet = result.scalars().first()

    # Если кошелька нет - исключение
    if not wallet:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail='Кошелек не найден'
        )

    return wallet
