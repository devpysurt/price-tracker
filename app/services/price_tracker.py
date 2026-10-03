import asyncio
import logging
import random
from decimal import Decimal, ROUND_HALF_UP
from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker
from app.config import Settings
from app.database import utcnow
from app.models import TrackedProduct, PriceHistory
from app.schemas.product import ProductOut
from app.services.notifications import NotificationService
from app.services.providers.base import ProductProvider

logger = logging.getLogger(__name__)

class TrackedNotFound(Exception):
    pass

class AlreadyTracked(Exception):
    pass

class PriceTracker:
    def __init__(self, sessions: sessionmaker, provider: ProductProvider,
                 notifications: NotificationService, settings: Settings):
        self.sessions = sessions
        self.provider = provider
        self.notifications = notifications
        self.settings = settings
        # One process is intentional: serialize scheduler/manual writes and alerts.
        self.lock = asyncio.Lock()

    def _get(self, session: Session, product_id: int) -> TrackedProduct:
        product = session.get(TrackedProduct, product_id)
        if product is None:
            raise TrackedNotFound("Tracked product not found")
        return product

    @staticmethod
    def serialize(product: TrackedProduct) -> ProductOut:
        prices = [point.price for point in product.history] or [product.current_price]
        change = product.current_price - prices[0]
        percent = ((change / prices[0] * 100).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
                   if prices[0] else None)
        values = {column.name: getattr(product, column.name) for column in product.__table__.columns}
        return ProductOut(**values, minimum_price=min(prices), maximum_price=max(prices),
                          first_price=prices[0], absolute_change=change, percentage_change=percent)

    def list_tracked(self) -> list[ProductOut]:
        with self.sessions() as session:
            return [self.serialize(p) for p in session.scalars(select(TrackedProduct).order_by(TrackedProduct.id.desc()))]

    def get(self, product_id: int) -> ProductOut:
        with self.sessions() as session:
            return self.serialize(self._get(session, product_id))

    def history(self, product_id: int) -> list[PriceHistory]:
        with self.sessions() as session:
            return list(self._get(session, product_id).history)

    async def _notify(self, product: TrackedProduct) -> None:
        if product.current_price > product.target_price:
            product.notification_sent = False
        elif not product.notification_sent:
            try:
                await self.notifications.send(product.title, product.current_price, product.target_price)
            except Exception:
                logger.exception("Notification failed for tracked product %s", product.id)
            else:
                product.notification_sent = True

    async def add(self, external_id: int, target: Decimal) -> ProductOut:
        async with self.lock:
            with self.sessions() as session:
                exists = session.scalar(select(TrackedProduct.id).where(
                    TrackedProduct.external_id == external_id, TrackedProduct.source == self.provider.source))
                if exists is not None:
                    raise AlreadyTracked("This product is already tracked")
            source = await self.provider.get_product(external_id)
            now = utcnow()
            with self.sessions.begin() as session:
                product = TrackedProduct(external_id=source.id, title=source.title,
                    thumbnail=str(source.thumbnail), source=self.provider.source,
                    current_price=source.price, target_price=target, last_checked_at=now,
                    notification_sent=False)
                product.history.append(PriceHistory(price=source.price, checked_at=now))
                session.add(product)
                session.flush()
                await self._notify(product)
                return self.serialize(product)

    async def refresh(self, product_id: int) -> ProductOut:
        async with self.lock:
            with self.sessions() as session:
                external_id = self._get(session, product_id).external_id
            source = await self.provider.get_product(external_id)
            price = source.price
            if self.settings.simulate_price_changes:
                price = (price * Decimal(random.randint(9500, 10500)) / 10000).quantize(
                    Decimal("0.01"), rounding=ROUND_HALF_UP)
            with self.sessions.begin() as session:
                product = self._get(session, product_id)
                product.current_price = price
                product.last_checked_at = utcnow()
                product.updated_at = product.last_checked_at
                product.history.append(PriceHistory(price=price, checked_at=product.last_checked_at))
                await self._notify(product)
                session.flush()
                return self.serialize(product)

    async def update_target(self, product_id: int, target: Decimal) -> ProductOut:
        async with self.lock:
            with self.sessions.begin() as session:
                product = self._get(session, product_id)
                if product.target_price != target:
                    product.target_price = target
                    product.notification_sent = False
                await self._notify(product)
                session.flush()
                return self.serialize(product)

    async def delete(self, product_id: int) -> None:
        async with self.lock:
            with self.sessions.begin() as session:
                session.delete(self._get(session, product_id))

    async def refresh_all(self) -> None:
        with self.sessions() as session:
            ids = list(session.scalars(select(TrackedProduct.id)))
        for product_id in ids:
            try:
                await self.refresh(product_id)
            except TrackedNotFound:
                continue
            except Exception:
                logger.exception("Price refresh failed for tracked product %s", product_id)
