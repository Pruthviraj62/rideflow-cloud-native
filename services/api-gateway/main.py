
import os
from contextlib import asynccontextmanager

import httpx
from fastapi import FastAPI, Request, Response
from fastapi.responses import JSONResponse

SERVICES = {
    "rider": os.getenv("RIDER_SERVICE_URL", "http://127.0.0.1:8002"),
    "driver": os.getenv("DRIVER_SERVICE_URL", "http://127.0.0.1:8004"),
    "pricing": os.getenv("PRICING_SERVICE_URL", "http://127.0.0.1:8006"),
    "trip": os.getenv("TRIP_SERVICE_URL", "http://127.0.0.1:8007"),
}

TIMEOUT = httpx.Timeout(10.0)


@asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.client = httpx.AsyncClient(timeout=TIMEOUT)
    yield
    await app.state.client.aclose()


app = FastAPI(
    title="RideFlow API Gateway",
    version="0.1.0",
    description="Single entry point for RideFlow microservices.",
    lifespan=lifespan,
)


@app.get("/health")
async def health():
    return {"status": "healthy", "service": "api-gateway"}


async def forward(
    request: Request,
    service: str,
    path: str,
) -> Response:
    url = f"{SERVICES[service].rstrip('/')}/{path.lstrip('/')}"

    try:
        body = await request.body()
        upstream = await request.app.state.client.request(
            method=request.method,
            url=url,
            params=request.query_params,
            content=body if body else None,
            headers={
                key: value
                for key, value in request.headers.items()
                if key.lower() not in {
                    "host", "content-length", "connection",
                    "transfer-encoding"
                }
            },
        )

        excluded = {
            "content-encoding",
            "content-length",
            "transfer-encoding",
            "connection",
        }
        headers = {
            key: value
            for key, value in upstream.headers.items()
            if key.lower() not in excluded
        }

        return Response(
            content=upstream.content,
            status_code=upstream.status_code,
            headers=headers,
        )

    except httpx.RequestError:
        return JSONResponse(
            status_code=502,
            content={
                "error": "upstream_service_unavailable",
                "service": service,
            },
        )


@app.api_route(
    "/riders",
    methods=["GET", "POST"],
)
async def riders(request: Request):
    return await forward(request, "rider", "/riders")


@app.api_route(
    "/riders/{rider_id}",
    methods=["GET", "PATCH", "DELETE"],
)
async def rider_by_id(request: Request, rider_id: str):
    return await forward(request, "rider", f"/riders/{rider_id}")


@app.api_route(
    "/drivers",
    methods=["GET", "POST"],
)
async def drivers(request: Request):
    return await forward(request, "driver", "/drivers")


@app.api_route(
    "/drivers/{driver_id}",
    methods=["GET", "PATCH", "DELETE"],
)
async def driver_by_id(request: Request, driver_id: str):
    return await forward(request, "driver", f"/drivers/{driver_id}")


@app.post("/fare/estimate")
async def estimate_fare(request: Request):
    return await forward(request, "pricing", "/fare/estimate")


@app.api_route(
    "/trips",
    methods=["GET", "POST"],
)
async def trips(request: Request):
    return await forward(request, "trip", "/trips")


@app.patch("/trips/{trip_id}/assign")
async def assign_trip_driver(request: Request, trip_id: str):
    return await forward(request, "trip", f"/trips/{trip_id}/assign")


@app.patch("/trips/{trip_id}/status")
async def update_trip_status(request: Request, trip_id: str):
    return await forward(request, "trip", f"/trips/{trip_id}/status")


@app.api_route(
    "/trips/{trip_id}",
    methods=["GET", "PATCH", "DELETE"],
)
async def trip_by_id(request: Request, trip_id: str):
    return await forward(request, "trip", f"/trips/{trip_id}")
