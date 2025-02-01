from decimal import Decimal

from pydantic import UUID4, BaseModel


class WalletResponse(BaseModel):
    id: int
    UUID: UUID4
    amount: Decimal

    class Config:
        from_attributes = True
