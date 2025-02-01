from sqlalchemy import DECIMAL, UUID, Column, Integer

from app.db import Base


class Wallet(Base):
    """ Модель кошелька """
    __tablename__ = 'wallets'

    id = Column(Integer, primary_key=True, index=True)
    UUID = Column(UUID(as_uuid=True), unique=True, nullable=False, index=True)
    amount = Column(DECIMAL, nullable=False, default=0)

    # __table_args__ = (
    #     UniqueConstraint('UUID', name='uq_wallet_uuid'),
    # )
