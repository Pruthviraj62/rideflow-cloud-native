import os
import uuid
from datetime import datetime, timezone
from decimal import Decimal, ROUND_HALF_UP
from enum import Enum

import httpx
from fastapi import FastAPI, HTTPException
from fastapi.responses import Response
from pydantic import BaseModel, Field
from sqlalchemy import create_engine, String, Float, DateTime
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, sessionmaker
from prometheus_client import Counter, generate_latest, CONTENT_TYPE_LATEST

SERVICE_NAME = "trip-service"
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:////app/data/rideflow_trips.db")
PRICING_SERVICE_URL = os.getenv(
    "PRICING_SERVICE_URL",
    "http://127.0.0.1:8003"
).rstrip("/")
RIDER_SERVICE_URL = os.getenv(
    "RIDER_SERVICE_URL", "http://127.0.0.1:8001"
).rstrip("/")
DRIVER_SERVICE_URL = os.getenv(
    "DRIVER_SERVICE_URL", "http://127.0.0.1:8002"
).rstrip("/")

engine_args = {"connect_args": {"check_same_thread": False}} if DATABASE_URL.startswith("sqlite") else {}
engine = create_engine(DATABASE_URL, **engine_args)
SessionLocal = sessionmaker(bind=engine, expire_on_commit=False)


class Base(DeclarativeBase):
    pass


class TripStatus(str, Enum):
    REQUESTED = "REQUESTED"
    ACCEPTED = "ACCEPTED"
    IN_PROGRESS = "IN_PROGRESS"
    COMPLETED = "COMPLETED"
    CANCELLED = "CANCELLED"


class TripRecord(Base):
    __tablename__ = "trips"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    rider_id: Mapped[str] = mapped_column(String(36), index=True)
    driver_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    pickup_location: Mapped[str] = mapped_column(String(255))
    dropoff_location: Mapped[str] = mapped_column(String(255))
    distance_km: Mapped[float] = mapped_column(Float)
    surge_multiplier: Mapped[float] = mapped_column(Float, default=1.0)
    estimated_fare: Mapped[float] = mapped_column(Float)
    status: Mapped[str] = mapped_column(String(30), default=TripStatus.REQUESTED.value)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))


Base.metadata.create_all(bind=engine)

app = FastAPI(
    title="RideFlow Trip Service",
    description="Trip booking and lifecycle management API.",
    version="0.1.0",
)

TRIP_REQUESTS = Counter("rideflow_trip_requests_total", "Total trip creation requests")
TRIP_ERRORS = Counter("rideflow_trip_errors_total", "Total trip creation errors")


class TripCreate(BaseModel):
    rider_id: str = Field(min_length=1, max_length=36)
    pickup_location: str = Field(min_length=2, max_length=255)
    dropoff_location: str = Field(min_length=2, max_length=255)
    distance_km: float = Field(gt=0, le=1000)
    surge_multiplier: float = Field(default=1.0, ge=1.0, le=5.0)


class TripAssign(BaseModel):
    driver_id: str = Field(min_length=1, max_length=36)


class TripStatusUpdate(BaseModel):
    status: TripStatus


class TripResponse(BaseModel):
    id: str
    rider_id: str
    driver_id: str | None
    pickup_location: str
    dropoff_location: str
    distance_km: float
    surge_multiplier: float
    estimated_fare: float
    status: str
    created_at: datetime
    updated_at: datetime


@app.get("/health")
def health():
    return {"status": "healthy", "service": SERVICE_NAME}


@app.get("/metrics")
def metrics():
    return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)


def to_response(trip: TripRecord) -> TripResponse:
    return TripResponse.model_validate(trip, from_attributes=True)


def fetch_service_record(base_url: str, resource: str, record_id: str):
    try:
        response = httpx.get(
            f"{base_url}/{resource}/{record_id}",
            timeout=5.0,
        )
        if response.status_code == 404:
            return None
        response.raise_for_status()
        record = response.json()
        if not isinstance(record, dict):
            raise ValueError("Service returned a non-object response")
        return record
    except (httpx.HTTPError, ValueError) as exc:
        raise HTTPException(
            status_code=502,
            detail=f"{resource.capitalize()} service is unavailable or returned an invalid response.",
        ) from exc


@app.post("/trips", response_model=TripResponse, status_code=201)
def create_trip(request: TripCreate):
    TRIP_REQUESTS.inc()

    rider = fetch_service_record(
        RIDER_SERVICE_URL, "riders", request.rider_id
    )
    if rider is None:
        TRIP_ERRORS.inc()
        raise HTTPException(status_code=404, detail="Rider not found")

    try:
        response = httpx.post(
            f"{PRICING_SERVICE_URL}/fare/estimate",
            json={
                "distance_km": request.distance_km,
                "surge_multiplier": request.surge_multiplier,
            },
            timeout=5.0,
        )
        response.raise_for_status()
        fare_data = response.json()
    except (httpx.HTTPError, ValueError) as exc:
        TRIP_ERRORS.inc()
        raise HTTPException(
            status_code=502,
            detail="Pricing service is unavailable or returned an invalid response.",
        ) from exc

    now = datetime.now(timezone.utc)
    trip = TripRecord(
        id=str(uuid.uuid4()),
        rider_id=request.rider_id,
        pickup_location=request.pickup_location,
        dropoff_location=request.dropoff_location,
        distance_km=request.distance_km,
        surge_multiplier=request.surge_multiplier,
        estimated_fare=float(
            Decimal(str(fare_data["estimated_fare"])).quantize(
                Decimal("0.01"), rounding=ROUND_HALF_UP
            )
        ),
        status=TripStatus.REQUESTED.value,
        created_at=now,
        updated_at=now,
    )

    with SessionLocal() as db:
        db.add(trip)
        db.commit()
        db.refresh(trip)
        return to_response(trip)


@app.get("/trips", response_model=list[TripResponse])
def list_trips():
    with SessionLocal() as db:
        trips = db.query(TripRecord).order_by(TripRecord.created_at.desc()).all()
        return [to_response(trip) for trip in trips]


@app.get("/trips/{trip_id}", response_model=TripResponse)
def get_trip(trip_id: str):
    with SessionLocal() as db:
        trip = db.get(TripRecord, trip_id)
        if not trip:
            raise HTTPException(status_code=404, detail="Trip not found")
        return to_response(trip)


@app.patch("/trips/{trip_id}/assign", response_model=TripResponse)
def assign_driver(trip_id: str, request: TripAssign):
    with SessionLocal() as db:
        trip = db.get(TripRecord, trip_id)
        if not trip:
            raise HTTPException(status_code=404, detail="Trip not found")
        if trip.status != TripStatus.REQUESTED.value:
            raise HTTPException(status_code=409, detail="Only requested trips can be assigned")

        driver = fetch_service_record(
            DRIVER_SERVICE_URL, "drivers", request.driver_id
        )
        if driver is None:
            raise HTTPException(status_code=404, detail="Driver not found")
        if driver.get("available") is not True:
            raise HTTPException(
                status_code=409,
                detail="Driver is unavailable",
            )

        trip.driver_id = request.driver_id
        trip.status = TripStatus.ACCEPTED.value
        trip.updated_at = datetime.now(timezone.utc)
        db.commit()
        db.refresh(trip)
        return to_response(trip)


@app.patch("/trips/{trip_id}/status", response_model=TripResponse)
def update_trip_status(trip_id: str, request: TripStatusUpdate):
    allowed_transitions = {
        TripStatus.ACCEPTED.value: {TripStatus.IN_PROGRESS.value, TripStatus.CANCELLED.value},
        TripStatus.IN_PROGRESS.value: {TripStatus.COMPLETED.value},
    }

    with SessionLocal() as db:
        trip = db.get(TripRecord, trip_id)
        if not trip:
            raise HTTPException(status_code=404, detail="Trip not found")

        if request.status.value not in allowed_transitions.get(trip.status, set()):
            raise HTTPException(
                status_code=409,
                detail=f"Invalid status transition: {trip.status} -> {request.status.value}",
            )

        trip.status = request.status.value
        trip.updated_at = datetime.now(timezone.utc)
        db.commit()
        db.refresh(trip)
        return to_response(trip)
