import os
from decimal import Decimal, ROUND_HALF_UP

from fastapi import FastAPI
from fastapi.responses import Response
from pydantic import BaseModel, Field
from prometheus_client import Counter, generate_latest, CONTENT_TYPE_LATEST

SERVICE_NAME = "pricing-service"

BASE_FARE = Decimal(os.getenv("BASE_FARE", "30"))
RATE_PER_KM = Decimal(os.getenv("RATE_PER_KM", "12"))
MIN_FARE = Decimal(os.getenv("MIN_FARE", "50"))

app = FastAPI(
    title="RideFlow Pricing Service",
    description="Fare estimation API for the RideFlow ride-hailing platform.",
    version="0.1.0",
)

FARE_REQUESTS = Counter(
    "rideflow_fare_requests_total",
    "Total number of fare estimation requests",
)
FARE_ERRORS = Counter(
    "rideflow_fare_errors_total",
    "Total number of invalid fare estimation requests",
)


class FareRequest(BaseModel):
    distance_km: float = Field(gt=0, le=1000, description="Trip distance in kilometres")
    surge_multiplier: float = Field(
        default=1.0,
        ge=1.0,
        le=5.0,
        description="Surge multiplier from 1.0 to 5.0",
    )


class FareResponse(BaseModel):
    distance_km: float
    base_fare: float
    rate_per_km: float
    minimum_fare: float
    surge_multiplier: float
    fare_before_surge: float
    estimated_fare: float
    currency: str


def money(value: Decimal) -> Decimal:
    return value.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


@app.get("/health")
def health():
    return {"status": "healthy", "service": SERVICE_NAME}


@app.get("/metrics")
def metrics():
    return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)


@app.post("/fare/estimate", response_model=FareResponse)
def estimate_fare(request: FareRequest):
    FARE_REQUESTS.inc()

    distance = Decimal(str(request.distance_km))
    surge = Decimal(str(request.surge_multiplier))

    fare_before_surge = max(
        MIN_FARE,
        BASE_FARE + (distance * RATE_PER_KM),
    )
    estimated_fare = money(fare_before_surge * surge)

    return FareResponse(
        distance_km=request.distance_km,
        base_fare=float(BASE_FARE),
        rate_per_km=float(RATE_PER_KM),
        minimum_fare=float(MIN_FARE),
        surge_multiplier=request.surge_multiplier,
        fare_before_surge=float(money(fare_before_surge)),
        estimated_fare=float(estimated_fare),
        currency="INR",
    )
