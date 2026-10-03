from datetime import datetime
from decimal import Decimal
from sqlalchemy import String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.database import Base, Money, UTCDateTime, utcnow

class TrackedProduct(Base):
    __tablename__ = "tracked_products"
    __table_args__ = (UniqueConstraint("source", "external_id"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    external_id: Mapped[int]
    title: Mapped[str] = mapped_column(String(300))
    thumbnail: Mapped[str]
    source: Mapped[str]
    current_price: Mapped[Decimal] = mapped_column(Money)
    target_price: Mapped[Decimal] = mapped_column(Money)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow, onupdate=utcnow)
    last_checked_at: Mapped[datetime] = mapped_column(UTCDateTime)
    notification_sent: Mapped[bool] = mapped_column(default=False)
    history: Mapped[list["PriceHistory"]] = relationship(
        back_populates="product", cascade="all, delete-orphan",
        order_by="PriceHistory.id", lazy="selectin")
