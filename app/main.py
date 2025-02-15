from contextlib import asynccontextmanager
from uuid import UUID

from fastapi import Depends, FastAPI, HTTPException, status
from sqlalchemy.exc import OperationalError, SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from app.bearer import verify_token
from app.db import Base, async_session, engine
from app.models import Wallet
from app.schemas import OperationType, WalletOperation, WalletResponse


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


@app.get('/api/v1/wallets/{wallet_uuid}',
         response_model=WalletResponse,
         summary='Получение состояния кошелька по UUID',
         dependencies=[Depends(verify_token)],
         tags=['Работа с кошельком'])
async def get_wallet(wallet_uuid: str, db: AsyncSession = Depends(get_session)):
    """ Получение кошелька по UUID """

    # Проверяем корректность UUID
    try:
        wallet_uuid = UUID(wallet_uuid)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail='Неверный формат UUID'
        )

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


@app.post('/api/v1/wallets/{wallet_uuid}/operation',
          response_model=WalletResponse,
          summary='Движение средств по UUID кошелька',
          dependencies=[Depends(verify_token)],
          tags=['Работа с кошельком'])
async def operations_with_wallet(wallet_uuid: str, operation: WalletOperation, db: AsyncSession = Depends(get_session)):
    """ Движение средств по UUID кошелька """

    # Проверяем корректность UUID
    try:
        wallet_uuid = UUID(wallet_uuid)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail='Неверный формат UUID'
        )

    max_retries = 5
    for attempt in range(max_retries):
        try:
            async with db.begin():
                # Запрос в базу
                query = select(Wallet).where(Wallet.UUID == wallet_uuid).with_for_update()
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
                # Проверяем переданное значение
                if operation.operationType == OperationType.DEPOSIT:
                    wallet.amount += operation.amount
                elif operation.operationType == OperationType.WITHDRAW:
                    if wallet.amount < operation.amount:
                        raise HTTPException(
                            status_code=status.HTTP_400_BAD_REQUEST,
                            detail='Недостаточно средств для снятия'
                        )
                    wallet.amount -= operation.amount
                db.add(wallet)

            # Обновляем запись в базе
            await db.commit()

            # Выходим из цикла при успешной операции
            break

        except OperationalError as e:
            # Обработка дедлоков и других ошибок
            await db.rollback()
            if "deadlock detected" in str(e).lower():
                if attempt < max_retries - 1:
                    continue  # Повторяем попытку
                else:
                    raise HTTPException(
                        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                        detail='Системная ошибка, попробуйте позже'
                    )
            else:
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail='Произошла ошибка при обработке операции'
                ) from e

        # Проброс исключений
        except HTTPException as e:
            raise e

        except SQLAlchemyError:
            await db.rollback()
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail='Произошла ошибка при обработке операции'
            ) from SQLAlchemyError

    else:
        # Если все попытки исчерпаны
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail='Не удалось обработать операцию после нескольких попыток'
        )

    return wallet
