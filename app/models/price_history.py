from datetime import datetime
from decimal import Decimal
from sqlalchemy import ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.database import Base, Money, UTCDateTime, utcnow

class PriceHistory(Base):
    __tablename__ = "price_history"
    id: Mapped[int] = mapped_column(primary_key=True)
    product_id: Mapped[int] = mapped_column(ForeignKey("tracked_products.id", ondelete="CASCADE"), index=True)
    price: Mapped[Decimal] = mapped_column(Money)
    checked_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow)
    product: Mapped["TrackedProduct"] = relationship(back_populates="history")
