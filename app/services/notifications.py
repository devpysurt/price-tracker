import logging
from abc import ABC, abstractmethod
from decimal import Decimal

logger = logging.getLogger(__name__)

class NotificationService(ABC):
    @abstractmethod
    async def send(self, title: str, price: Decimal, target: Decimal) -> None:
        ...

class ConsoleNotificationService(NotificationService):
    async def send(self, title: str, price: Decimal, target: Decimal) -> None:
        logger.info("PRICE ALERT: %s reached $%.2f. Target price: $%.2f", title, price, target)
