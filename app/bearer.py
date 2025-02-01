from decouple import config
from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

security = HTTPBearer()


async def verify_token(credentials: HTTPAuthorizationCredentials = Depends(security)):
    """ Верификация Bearer """

    bearer_key = config('bearer_key')

    if credentials.scheme != "Bearer" or credentials.credentials != bearer_key:
        raise HTTPException(status_code=403, detail="Неверный или отсутствующий токен")
