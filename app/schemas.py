from decimal import Decimal

from pydantic import UUID4, BaseModel


class WalletResponse(BaseModel):
    id: int
    UUID: UUID4
    amount: Decimal

    class Config:
        from_attributes = True


class WalletOperation(BaseModel):
    operationType: str
    amount: Decimal

    class Config:
        from_attributes = True
