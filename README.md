# API для работы с кошельком

### Запуск вручную

```
    1) Измените название .env.simple на .env
    2) Заполните .env данными
    3) Запустите сервер "uvicorn app.main:app --host 0.0.0.0 --port 8000"
```

### Запуск через Docker-Compose

```
    1) Измените название .env.simple на .env
    2) Заполните .env данными
    3) Выполните команду "docker-compose up -d --build"
```

### Маршруты

```
    "docs/" - Документация
    "redoc/" - Документация
    "/api/v1/wallets/{wallet_uuid}" - Получение данных о кошельке
    "/api/v1/wallets/{wallet_uuid}/operation" - Операции с кошельком
```
