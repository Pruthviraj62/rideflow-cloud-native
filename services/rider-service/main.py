
import os
import uuid
from contextlib import asynccontextmanager
from datetime import datetime, timezone

from fastapi import Depends, FastAPI, HTTPException, Response, status
from pydantic import BaseModel, ConfigDict, EmailStr, Field
from prometheus_client import CONTENT_TYPE_LATEST, Counter, generate_latest
from sqlalchemy import DateTime, String, create_engine, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column, sessionmaker


DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:////app/data/rideflow_riders.db")

if DATABASE_URL.startswith("postgresql://"):
    DATABASE_URL = DATABASE_URL.replace(
        "postgresql://", "postgresql+psycopg://", 1
    )

engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False}
    if DATABASE_URL.startswith("sqlite")
    else {},
)

SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


class Base(DeclarativeBase):
    pass


class RiderRecord(Base):
    __tablename__ = "riders"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    full_name: Mapped[str] = mapped_column(String(120), nullable=False)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    phone: Mapped[str] = mapped_column(String(30), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )


class RiderCreate(BaseModel):
    full_name: str = Field(min_length=2, max_length=120)
    email: EmailStr
    phone: str = Field(min_length=7, max_length=30)


class RiderUpdate(BaseModel):
    full_name: str | None = Field(default=None, min_length=2, max_length=120)
    email: EmailStr | None = None
    phone: str | None = Field(default=None, min_length=7, max_length=30)


class RiderResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    full_name: str
    email: EmailStr
    phone: str
    created_at: datetime
    updated_at: datetime


REQUESTS = Counter(
    "rider_service_requests_total",
    "Total HTTP requests handled by the Rider Service",
    ["method", "endpoint", "status"],
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    Base.metadata.create_all(bind=engine)
    yield
    engine.dispose()


app = FastAPI(
    title="RideFlow Rider Service",
    version="0.1.0",
    description="Rider profile management API for RideFlow.",
    lifespan=lifespan,
)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@app.get("/health")
def health():
    return {"status": "healthy", "service": "rider-service"}


@app.get("/metrics")
def metrics():
    return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)


@app.post(
    "/riders",
    response_model=RiderResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_rider(payload: RiderCreate, db: Session = Depends(get_db)):
    rider = RiderRecord(
        id=str(uuid.uuid4()),
        full_name=payload.full_name,
        email=str(payload.email).lower(),
        phone=payload.phone,
    )
    db.add(rider)

    try:
        db.commit()
        db.refresh(rider)
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=409, detail="A rider with this email already exists"
        )

    return rider


@app.get("/riders", response_model=list[RiderResponse])
def list_riders(db: Session = Depends(get_db)):
    return db.scalars(select(RiderRecord).order_by(RiderRecord.created_at)).all()


@app.get("/riders/{rider_id}", response_model=RiderResponse)
def get_rider(rider_id: str, db: Session = Depends(get_db)):
    rider = db.get(RiderRecord, rider_id)
    if rider is None:
        raise HTTPException(status_code=404, detail="Rider not found")
    return rider


@app.patch("/riders/{rider_id}", response_model=RiderResponse)
def update_rider(
    rider_id: str,
    payload: RiderUpdate,
    db: Session = Depends(get_db),
):
    rider = db.get(RiderRecord, rider_id)
    if rider is None:
        raise HTTPException(status_code=404, detail="Rider not found")

    updates = payload.model_dump(exclude_unset=True)
    for field, value in updates.items():
        if value is not None:
            setattr(rider, field, str(value).lower() if field == "email" else value)

    try:
        db.commit()
        db.refresh(rider)
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=409, detail="A rider with this email already exists"
        )

    return rider


@app.delete("/riders/{rider_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_rider(rider_id: str, db: Session = Depends(get_db)):
    rider = db.get(RiderRecord, rider_id)
    if rider is None:
        raise HTTPException(status_code=404, detail="Rider not found")

    db.delete(rider)
    db.commit()
