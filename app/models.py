from sqlalchemy import DECIMAL, UUID, Column, Integer

from app.db import Base


class Wallet(Base):
    """ Модель кошелька """
    __tablename__ = 'wallets'

    id = Column(Integer, primary_key=True, index=True)
    UUID = Column(UUID(as_uuid=True), unique=True, nullable=False, index=True)
    amount = Column(DECIMAL(10, 2), nullable=False, default=0)
