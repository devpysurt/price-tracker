import asyncio
from decimal import Decimal
import pytest
from fastapi.testclient import TestClient
from app.main import create_app
from app.config import Settings
from app.services.notifications import ConsoleNotificationService
from conftest import FakeProvider, RecordingNotifications

async def test_notification_crossing_and_target_change(setup):
    _, tracker, provider, notifications = setup
    product = await tracker.add(1, Decimal("100"))
    assert len(notifications.messages) == 1  # Equality triggers alert on add.
    await tracker.refresh(product.id)
    await tracker.update_target(product.id, Decimal("100"))
    assert len(notifications.messages) == 1
    provider.price = Decimal("110")
    await tracker.refresh(product.id)
    provider.price = Decimal("99")
    await tracker.refresh(product.id)
    assert len(notifications.messages) == 2
    await tracker.update_target(product.id, Decimal("105"))
    assert len(notifications.messages) == 3

async def test_simulation_uses_api_base(setup, monkeypatch):
    _, tracker, _, _ = setup
    tracker.settings.simulate_price_changes = True
    product = await tracker.add(1, Decimal("50"))
    monkeypatch.setattr("app.services.price_tracker.random.randint", lambda a,b:10500)
    assert (await tracker.refresh(product.id)).current_price == Decimal("105.00")
    assert (await tracker.refresh(product.id)).current_price == Decimal("105.00")
    monkeypatch.setattr("app.services.price_tracker.random.randint", lambda a,b:9500)
    assert (await tracker.refresh(product.id)).current_price == Decimal("95.00")
    assert len(tracker.history(product.id)) == 4

async def test_batch_continues_after_failure(setup, caplog):
    _, tracker, provider, _ = setup
    first = await tracker.add(1, Decimal("50"))
    second = await tracker.add(2, Decimal("50"))
    provider.failed_ids.add(1)
    await tracker.refresh_all()
    assert len(tracker.history(first.id)) == 1
    assert len(tracker.history(second.id)) == 2
    assert "Price refresh failed" in caplog.text

async def test_notification_failure_retries_without_losing_price(setup):
    _, tracker, _, notifications = setup
    notifications.fail = True
    product = await tracker.add(1, Decimal("110"))
    assert not product.notification_sent
    assert len(tracker.history(product.id)) == 1
    notifications.fail = False
    assert (await tracker.refresh(product.id)).notification_sent
    assert len(notifications.messages) == 1

async def test_zero_price_and_exact_cents(setup):
    _, tracker, provider, _ = setup
    provider.price = Decimal("0.00")
    product = await tracker.add(1, Decimal("0.29"))
    assert product.percentage_change is None
    provider.price = Decimal("0.29")
    await tracker.refresh(product.id)
    assert tracker.get(product.id).current_price == Decimal("0.29")

async def test_concurrent_refresh_serializes_alerts(setup):
    _, tracker, provider, notifications = setup
    product = await tracker.add(1, Decimal("90"))
    provider.price = Decimal("80")
    await asyncio.gather(tracker.refresh(product.id), tracker.refresh(product.id))
    assert len(tracker.history(product.id)) == 3
    assert len(notifications.messages) == 1

async def test_console_notification(caplog):
    import logging
    with caplog.at_level(logging.INFO):
        await ConsoleNotificationService().send("Phone", Decimal("99"), Decimal("100"))
    assert "PRICE ALERT: Phone reached $99.00. Target price: $100.00" in caplog.text

def test_scheduler_runs_and_stops(tmp_path):
    import time
    config = Settings(_env_file=None, database_url=f"sqlite:///{tmp_path}/job.db",
                      scheduler_enabled=True, price_check_interval_seconds=1,
                      simulate_price_changes=False)
    app = create_app(config, FakeProvider(), RecordingNotifications())
    with TestClient(app) as client:
        product = client.post("/api/tracked",json={"external_id":1,"target_price":50}).json()
        assert app.state.scheduler.running
        deadline = time.monotonic() + 5
        while time.monotonic() < deadline:
            history = client.get(f"/api/tracked/{product['id']}/history").json()
            if len(history) >= 2:
                break
            time.sleep(.1)
        assert len(history) >= 2
    assert not app.state.scheduler.running
