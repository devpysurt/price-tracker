from decimal import Decimal
import pytest
from sqlalchemy import select, func
from app.models import PriceHistory

def add(client, target="90.00"):
    response = client.post("/api/tracked", json={"external_id": 1, "target_price": target})
    assert response.status_code == 201
    return response.json()

def test_health_and_pages(setup):
    client, *_ = setup
    assert client.get("/api/health").json() == {"status": "ok"}
    assert client.get("/").status_code == 200
    assert client.get("/docs").status_code == 200
    schema = client.get("/openapi.json").json()
    assert "/api/tracked/{product_id}/refresh" in schema["paths"]
    assert client.get("/static/app.js").status_code == 200

def test_full_tracking_lifecycle(setup):
    client, tracker, provider, notifications = setup
    assert client.get("/api/products/search?q=phone").json()["total"] == 1
    assert client.get("/api/products/search").json()["total"] == 1
    product = add(client)
    path = f"/api/tracked/{product['id']}"
    assert len(client.get("/api/tracked").json()) == 1
    assert client.get(path).json()["first_price"] == "100.00"
    assert len(client.get(path + "/history").json()) == 1
    assert client.get(f"/products/{product['id']}").status_code == 200
    assert product["last_checked_at"].endswith("Z")
    provider.price = Decimal("80.00")
    refreshed = client.post(path + "/refresh").json()
    assert refreshed["minimum_price"] == "80.00"
    assert refreshed["maximum_price"] == "100.00"
    assert refreshed["absolute_change"] == "-20.00"
    assert refreshed["percentage_change"] == "-20.00"
    assert len(client.get(path + "/history").json()) == 2
    assert len(notifications.messages) == 1
    patched = client.patch(path, json={"target_price": "70.25"})
    assert patched.status_code == 200
    assert patched.json()["target_price"] == "70.25"
    assert not patched.json()["notification_sent"]
    assert client.delete(path).status_code == 204
    assert client.get(path).status_code == 404
    assert client.get(path + "/history").status_code == 404
    assert client.get("/api/tracked").json() == []
    with tracker.sessions() as session:
        assert session.scalar(select(func.count()).select_from(PriceHistory)) == 0

def test_duplicate_and_missing(setup):
    client, *_ = setup
    add(client)
    assert client.post("/api/tracked", json={"external_id":1,"target_price":90}).status_code == 409
    assert client.post("/api/tracked/999/refresh").status_code == 404
    assert client.patch("/api/tracked/999", json={"target_price":90}).status_code == 404
    assert client.delete("/api/tracked/999").status_code == 404
    assert client.get("/products/999").status_code == 404

@pytest.mark.parametrize("price", ["-1", "1.001", "NaN", "Infinity", "1000000000"])
def test_invalid_target(setup, price):
    client, *_ = setup
    assert client.post("/api/tracked", json={"external_id":1,"target_price":price}).status_code == 422

def test_provider_failure_preserves_history(setup):
    client, tracker, provider, _ = setup
    product = add(client)
    provider.failed_ids.add(1)
    path = f"/api/tracked/{product['id']}"
    assert client.post(path + "/refresh").status_code == 502
    assert len(client.get(path + "/history").json()) == 1
    assert client.get(path).json()["last_checked_at"] == product["last_checked_at"]
    assert client.get("/api/health").status_code == 200
