
import os
import uuid
from datetime import datetime, timezone

from fastapi import FastAPI, HTTPException, Response
from pydantic import BaseModel, Field
from sqlalchemy import Boolean, DateTime, String, create_engine
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, sessionmaker
from prometheus_client import Counter, generate_latest, CONTENT_TYPE_LATEST

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./rideflow_drivers.db")

engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {},
)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)


class Base(DeclarativeBase):
    pass


class DriverRecord(Base):
    __tablename__ = "drivers"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    full_name: Mapped[str] = mapped_column(String(120), nullable=False)
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    phone: Mapped[str] = mapped_column(String(20), nullable=False)
    vehicle_model: Mapped[str] = mapped_column(String(100), nullable=False)
    vehicle_number: Mapped[str] = mapped_column(String(20), unique=True, nullable=False)
    available: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))


Base.metadata.create_all(bind=engine)

app = FastAPI(
    title="RideFlow Driver Service",
    description="Driver profiles, vehicle details, and availability management.",
    version="0.1.0",
)

REQUESTS = Counter("driver_service_requests_total", "Driver service requests", ["operation"])


class DriverCreate(BaseModel):
    full_name: str = Field(min_length=2, max_length=120)
    email: str
    phone: str = Field(min_length=7, max_length=20)
    vehicle_model: str = Field(min_length=2, max_length=100)
    vehicle_number: str = Field(min_length=3, max_length=20)


class DriverUpdate(BaseModel):
    phone: str | None = Field(default=None, min_length=7, max_length=20)
    vehicle_model: str | None = Field(default=None, min_length=2, max_length=100)
    available: bool | None = None


def serialize_driver(driver: DriverRecord) -> dict:
    return {
        "id": driver.id,
        "full_name": driver.full_name,
        "email": driver.email,
        "phone": driver.phone,
        "vehicle_model": driver.vehicle_model,
        "vehicle_number": driver.vehicle_number,
        "available": driver.available,
        "created_at": driver.created_at.isoformat() if driver.created_at else None,
    }


@app.get("/health")
def health():
    return {"status": "healthy", "service": "driver-service"}


@app.get("/metrics")
def metrics():
    return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)


@app.post("/drivers", status_code=201)
def create_driver(payload: DriverCreate):
    REQUESTS.labels("create").inc()
    with SessionLocal() as db:
        existing = db.query(DriverRecord).filter(
            (DriverRecord.email == payload.email) |
            (DriverRecord.vehicle_number == payload.vehicle_number)
        ).first()
        if existing:
            raise HTTPException(status_code=409, detail="Email or vehicle number already registered")

        driver = DriverRecord(**payload.model_dump())
        db.add(driver)
        db.commit()
        db.refresh(driver)
        return serialize_driver(driver)


@app.get("/drivers")
def list_drivers():
    REQUESTS.labels("list").inc()
    with SessionLocal() as db:
        return [serialize_driver(d) for d in db.query(DriverRecord).order_by(DriverRecord.created_at.desc()).all()]


@app.get("/drivers/{driver_id}")
def get_driver(driver_id: str):
    REQUESTS.labels("get").inc()
    with SessionLocal() as db:
        driver = db.get(DriverRecord, driver_id)
        if not driver:
            raise HTTPException(status_code=404, detail="Driver not found")
        return serialize_driver(driver)


@app.patch("/drivers/{driver_id}")
def update_driver(driver_id: str, payload: DriverUpdate):
    REQUESTS.labels("update").inc()
    changes = payload.model_dump(exclude_unset=True)
    if not changes:
        raise HTTPException(status_code=400, detail="No update fields supplied")

    with SessionLocal() as db:
        driver = db.get(DriverRecord, driver_id)
        if not driver:
            raise HTTPException(status_code=404, detail="Driver not found")
        for field, value in changes.items():
            setattr(driver, field, value)
        db.commit()
        db.refresh(driver)
        return serialize_driver(driver)


@app.delete("/drivers/{driver_id}", status_code=204)
def delete_driver(driver_id: str):
    REQUESTS.labels("delete").inc()
    with SessionLocal() as db:
        driver = db.get(DriverRecord, driver_id)
        if not driver:
            raise HTTPException(status_code=404, detail="Driver not found")
        db.delete(driver)
        db.commit()
    return Response(status_code=204)
