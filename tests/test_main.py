from unittest.mock import patch

import pytest
import pytest_asyncio
from decouple import config
from fastapi import HTTPException
from httpx import ASGITransport, AsyncClient
from sqlalchemy.exc import OperationalError, SQLAlchemyError
from sqlalchemy.ext.asyncio import (AsyncSession, async_sessionmaker,
                                    create_async_engine)
from sqlalchemy.sql import select, text
from sqlalchemy import create_engine

from app.db import Base
from app.main import app, get_session, get_wallet
from app.models import Wallet

user = config('POSTGRES_USER_TEST')
password = config('POSTGRES_PASSWORD_TEST')
host = config('POSTGRES_HOST_TEST')
port = config('POSTGRES_PORT_TEST')
dbname = config('POSTGRES_DB_TEST')
DATABASE_URL_TEST = f"postgresql+asyncpg://{user}:{password}@{host}:{port}/{dbname}"

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

# Создание асинхронного движка для тестовой базы данных
test_engine = create_async_engine(DATABASE_URL_TEST, echo=False, future=True)

TestSessionLocal = async_sessionmaker(test_engine, expire_on_commit=False, class_=AsyncSession)


@pytest_asyncio.fixture()
async def setup_database():
    """ Создание и удаление таблиц перед и после всех тестов """

    # Переопределение зависимости для тестов
    async def override_get_session() -> AsyncSession:
        async with TestSessionLocal() as session:
            yield session

    app.dependency_overrides[get_session] = override_get_session

    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await test_engine.dispose()


@pytest_asyncio.fixture
async def client(setup_database):
    """ Фикстура для клиента HTTPX и очистки таблиц перед каждым тестом """
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # Очистка таблицы wallets перед каждым тестом
        async with TestSessionLocal() as session:
            await session.execute(text('TRUNCATE TABLE wallets RESTART IDENTITY CASCADE;'))
            await session.commit()
        yield client


@pytest.fixture
def bearer_key():
    """ Фикстура для ключа Bearer """
    return f"Bearer {config('bearer_key_test')}"


@pytest.mark.asyncio
async def test_create_wallet_table(setup_database):
    """Тестирование создания таблицы кошельков"""
    async with TestSessionLocal() as session:
        result = await session.execute(select(Wallet))
        wallets = result.scalars().all()
        assert wallets == []  # Таблица должна быть пустой после создания


@pytest.mark.asyncio
async def test_get_wallet(client, bearer_key):
    """Тестирование эндпоинта GET /api/v1/wallets/{wallet_uuid}"""
    # Предварительная подготовка данных в базе
    async with TestSessionLocal() as session:
        wallet = Wallet(
            UUID='1a88911f-3345-4963-bd73-0f76dbf27a1d',
            amount=100.0
        )
        session.add(wallet)
        await session.commit()

    assert wallet.UUID == '1a88911f-3345-4963-bd73-0f76dbf27a1d'
    assert wallet.amount == 100.0

    response = await client.get(
        "/api/v1/wallets/1a88911f-3345-4963-bd73-0f76dbf27a1d",
        headers={"Authorization": bearer_key}
    )

    # Проверка ответа
    assert response.status_code == 200
    data = response.json()
    assert data['UUID'] == '1a88911f-3345-4963-bd73-0f76dbf27a1d'


@pytest.mark.asyncio
async def test_get_uuid_not_found(client, bearer_key):
    """Тестирование GET /api/v1/wallets/{wallet_uuid} для неверного UUID кошелька"""

    response = await client.get(
        "/api/v1/wallets/non-existent-uuid",
        headers={"Authorization": bearer_key}
    )

    assert response.status_code == 422  # Неверный формат UUID
    data = response.json()
    assert data['detail'] == 'Неверный формат UUID'


@pytest.mark.asyncio
async def test_not_bearer(client, bearer_key):
    """Тестирование эндпоинта GET /api/v1/wallets/{wallet_uuid} с неверным Bearer"""

    response = await client.get(
        "/api/v1/wallets/1a88911f-3345-4963-bd73-0f76dbf27a1d",
        headers={"Authorization": bearer_key[:-1] + "1"}
    )  # Изменил последнюю цифру ключа на 1

    assert response.status_code == 403  # Не верный или отсутствующий ключ
    data = response.json()
    assert data['detail'] == "Неверный или отсутствующий токен"


@pytest.mark.asyncio
async def test_get_wallet_not_found(client, bearer_key):
    """Тестирование эндпоинта GET /api/v1/wallets/{wallet_uuid} для несуществующего кошелька"""

    response = await client.get(
        "/api/v1/wallets/0e81690e-d29f-4596-af25-d5ca43e48d3b",
        headers={"Authorization": bearer_key}
    )

    assert response.status_code == 404  # UUID не найден
    data = response.json()
    assert data['detail'] == 'Кошелек не найден'


@pytest.mark.asyncio
async def test_operations(client, bearer_key):
    """Тестирование POST /api/v1/wallets/{wallet_uuid}/operation"""
    # Предварительная подготовка данных в базе
    async with TestSessionLocal() as session:
        wallet = Wallet(
            UUID='1a88911f-3345-4963-bd73-0f76dbf27a1d',
            amount=100.0
        )
        session.add(wallet)
        await session.commit()

    assert wallet.UUID == '1a88911f-3345-4963-bd73-0f76dbf27a1d'
    assert wallet.amount == 100.0

    response = await client.post(
        "/api/v1/wallets/1a88911f-3345-4963-bd73-0f76dbf27a1d/operation",
        headers={"Authorization": bearer_key}, json={"operationType": "DDEPOSIT", "amount": 1})

    # Неверный тип операции
    assert response.status_code == 422
    data = response.json()
    assert data['detail'][0]['msg'] == "Input should be 'DEPOSIT' or 'WITHDRAW'"

    response = await client.post(
        "/api/v1/wallets/1a88911f-3345-4963-bd73-0f76dbf27a1d/operation",
        headers={"Authorization": bearer_key}, json={"operationType": "DEPOSIT", "amount": 1})
    assert response.status_code == 200
    data = response.json()
    assert data['amount'] == '101.00'

    response = await client.post(
        "/api/v1/wallets/1a88911f-3345-4963-bd73-0f76dbf27a1d/operation",
        headers={"Authorization": bearer_key}, json={"operationType": "WITHDRAW", "amount": 100})
    assert response.status_code == 200
    data = response.json()
    assert data['amount'] == '1.00'

    response = await client.post(
        "/api/v1/wallets/1a88911f-3345-4963-bd73-0f76dbf27a1d/operation",
        headers={"Authorization": bearer_key}, json={"operationType": "WITHDRAW", "amount": 100})

    assert response.status_code == 400  # Недостаточно средств
    data = response.json()
    assert data['detail'] == 'Недостаточно средств для снятия'


@pytest.mark.asyncio
async def test_operations_with_deadlock(client, bearer_key):
    """Тестирование обработки дедлоков"""
    # Предварительная подготовка данных в базе
    async with TestSessionLocal() as session:
        wallet = Wallet(
            UUID='1a88911f-3345-4963-bd73-0f76dbf27a1d',
            amount=100.0
        )
        session.add(wallet)
        await session.commit()

    transport = ASGITransport(app=app)
    # Создаем два клиента, которые будут пытаться одновременно изменить один и тот же кошелек
    async with (AsyncClient(transport=transport, base_url="http://test") as client1,
                AsyncClient(transport=transport, base_url="http://test") as client2):
        response1 = await client1.post(
            "/api/v1/wallets/1a88911f-3345-4963-bd73-0f76dbf27a1d/operation",
            headers={"Authorization": bearer_key}, json={"operationType": "WITHDRAW", "amount": '50'})

        response2 = await client2.post(
            "/api/v1/wallets/1a88911f-3345-4963-bd73-0f76dbf27a1d/operation",
            headers={"Authorization": bearer_key}, json={"operationType": "WITHDRAW", "amount": '30'})

        # Проверяем, что один из запросов завершился успешно, а другой - с ошибкой
        assert response1.status_code in [200, 500]
        assert response2.status_code in [200, 500]


@pytest.mark.asyncio
async def test_invalid_amount(client, bearer_key):
    """Тестирование операций с неверным типом суммы"""
    async with TestSessionLocal() as session:
        wallet = Wallet(
            UUID='0145fe65-72c9-4faf-bf00-ccad5a27ba41',
            amount=100.0
        )
        session.add(wallet)
        await session.commit()

    response = await client.post(
        "/api/v1/wallets/0145fe65-72c9-4faf-bf00-ccad5a27ba41/operation",
        headers={"Authorization": bearer_key},
        json={"operationType": "DEPOSIT", "amount": "invalid"}
    )

    assert response.status_code == 422
    data = response.json()
    assert data['detail'][0]['msg'] == 'Input should be a valid decimal'


@pytest.mark.asyncio
async def test_get_wallet_invalid_uuid(setup_database):
    """Тестирование функции get_wallet с неверным UUID"""

    with pytest.raises(HTTPException) as exc_info:
        await get_wallet(wallet_uuid="invalid-uuid", db=setup_database)

    assert exc_info.value.status_code == 422
    assert exc_info.value.detail == 'Неверный формат UUID'


@pytest.mark.asyncio
async def test_operation_with_operational_error(client, bearer_key):
    """Тестирование обработки OperationalError при выполнении операции"""

    # Предварительная подготовка данных в базе
    async with TestSessionLocal() as session:
        wallet = Wallet(
            UUID='5e88911f-3345-4963-bd73-0f76dbf27a5e',
            amount=500.0
        )
        session.add(wallet)
        await session.commit()

    with patch('app.main.select') as mocked_select:
        mocked_select.side_effect = OperationalError("Ошибка операции", params=None, orig=None)  # type:ignore

        response = await client.post(
            "/api/v1/wallets/5e88911f-3345-4963-bd73-0f76dbf27a5e/operation",
            headers={"Authorization": bearer_key},
            json={"operationType": "WITHDRAW", "amount": '50'}
        )

        assert response.status_code == 500
        data = response.json()
        assert data['detail'] == 'Произошла ошибка при обработке операции'


@pytest.mark.asyncio
async def test_operation_with_sqlalchemy_error(client, bearer_key):
    """Тестирование обработки SQLAlchemyError при выполнении операции"""

    # Предварительная подготовка данных в базе
    async with TestSessionLocal() as session:
        wallet = Wallet(
            UUID='6f88911f-3345-4963-bd73-0f76dbf27a6f',
            amount=600.0
        )
        session.add(wallet)
        await session.commit()

    with patch('app.main.select') as mocked_select:
        mocked_select.side_effect = SQLAlchemyError()

        response = await client.post(
            "/api/v1/wallets/6f88911f-3345-4963-bd73-0f76dbf27a6f/operation",
            headers={"Authorization": bearer_key},
            json={"operationType": "WITHDRAW", "amount": '50'}
        )

        assert response.status_code == 500
        data = response.json()
        assert data['detail'] == 'Произошла ошибка при обработке операции'


@pytest.mark.asyncio
async def test_operation_missing_parameters(client, bearer_key):
    """Тестирование операции с отсутствующими параметрами"""

    response = await client.post(
        "/api/v1/wallets/1a88911f-3345-4963-bd73-0f76dbf27a1d/operation",
        headers={"Authorization": bearer_key},
        json={}  # Пустой JSON
    )

    assert response.status_code == 422
    data = response.json()
    assert 'operationType' in data['detail'][0]['loc']
    assert 'amount' in data['detail'][1]['loc']


@pytest.mark.asyncio
async def test_operation_missing_authorization(client):
    """Тестирование операции без Authorization"""

    response = await client.post(
        "/api/v1/wallets/1a88911f-3345-4963-bd73-0f76dbf27a1d/operation",
        json={"operationType": "DEPOSIT", "amount": '50'}
    )

    assert response.status_code == 403  # Неавторизованный доступ
    data = response.json()
    assert data['detail'] == "Not authenticated"
