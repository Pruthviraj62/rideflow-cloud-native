import importlib.util
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

SERVICE_PATH = (
    Path(__file__).resolve().parents[1]
    / "services"
    / "pricing-service"
    / "main.py"
)

spec = importlib.util.spec_from_file_location("pricing_service_main", SERVICE_PATH)
pricing = importlib.util.module_from_spec(spec)
spec.loader.exec_module(pricing)

client = TestClient(pricing.app)


def test_health_endpoint():
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {
        "status": "healthy",
        "service": "pricing-service",
    }


def test_standard_fare():
    response = client.post(
        "/fare/estimate",
        json={"distance_km": 10, "surge_multiplier": 1},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["fare_before_surge"] == 150
    assert data["estimated_fare"] == 150
    assert data["currency"] == "INR"


def test_minimum_fare():
    response = client.post(
        "/fare/estimate",
        json={"distance_km": 1, "surge_multiplier": 1},
    )
    assert response.status_code == 200
    assert response.json()["estimated_fare"] == 50


def test_surge_pricing():
    response = client.post(
        "/fare/estimate",
        json={"distance_km": 10, "surge_multiplier": 2},
    )
    assert response.status_code == 200
    assert response.json()["estimated_fare"] == 300


@pytest.mark.parametrize(
    "payload",
    [
        {"distance_km": 0},
        {"distance_km": -1},
        {"distance_km": 1001},
        {"distance_km": 5, "surge_multiplier": 0.5},
        {"distance_km": 5, "surge_multiplier": 6},
        {},
    ],
)
def test_invalid_fare_requests(payload):
    response = client.post("/fare/estimate", json=payload)
    assert response.status_code == 422
