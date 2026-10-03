from decimal import Decimal
import pytest
from fastapi.testclient import TestClient
from app.config import Settings
from app.main import create_app
from app.schemas.product import ProviderProduct, SearchResult
from app.services.providers.base import ProductProvider, ProviderError
from app.services.notifications import NotificationService

class FakeProvider(ProductProvider):
    source = "fake"
    def __init__(self):
        self.price = Decimal("100.00")
        self.failed_ids = set()
    async def get_product(self, product_id):
        if product_id in self.failed_ids:
            raise ProviderError("Temporarily unavailable")
        return ProviderProduct(id=product_id, title=f"Phone {product_id}",
                               thumbnail="https://example.com/phone.png", price=self.price)
    async def search(self, query, limit, skip):
        products = [await self.get_product(1)] if query.lower() in "phone" else []
        return SearchResult(products=products[skip:skip+limit], total=len(products), skip=skip, limit=limit)

class RecordingNotifications(NotificationService):
    def __init__(self):
        self.messages = []
        self.fail = False
    async def send(self, title, price, target):
        if self.fail:
            raise RuntimeError("Notification unavailable")
        self.messages.append((title, price, target))

@pytest.fixture
def setup(tmp_path):
    provider, notifications = FakeProvider(), RecordingNotifications()
    settings = Settings(_env_file=None, database_url=f"sqlite:///{tmp_path}/test.db",
                        simulate_price_changes=False, scheduler_enabled=False)
    app = create_app(settings, provider, notifications)
    with TestClient(app) as client:
        yield client, app.state.tracker, provider, notifications
