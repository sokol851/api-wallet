from decimal import Decimal
from enum import Enum

from pydantic import UUID4, BaseModel, ConfigDict


class OperationType(str, Enum):
    DEPOSIT = "DEPOSIT"
    WITHDRAW = "WITHDRAW"


class WalletResponse(BaseModel):
    id: int
    UUID: UUID4
    amount: Decimal

    model_config = ConfigDict(from_attributes=True)


class WalletOperation(BaseModel):
    operationType: OperationType
    amount: Decimal

    model_config = ConfigDict(from_attributes=True)
