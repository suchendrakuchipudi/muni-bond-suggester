

"""
Production-grade Treasury Yield Data Engine
------------------------------------------
Features:
- Fetch Treasury yield curve data from FRED
- Store historical yields locally in PostgreSQL
- Compute derived analytics/spreads
- Expose REST API with FastAPI
- Serve a dashboard page for end users

Run locally:
1. Install PostgreSQL
2. Create database: treasury_engine
3. pip install -r requirements.txt
4. uvicorn treasury_data_engine:app --reload

Optional:
- Install TimescaleDB extension
- Add Docker later
"""

from datetime import date, datetime, timedelta
from typing import List

import importlib.util
import os
import socket
import statistics
from pathlib import Path

import httpx
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pydantic import BaseModel
from sqlalchemy import (
    Column,
    Date,
    DateTime,
    Float,
    Integer,
    String,
    UniqueConstraint,
    create_engine,
)
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import declarative_base
from sqlalchemy.orm import sessionmaker


# ============================================================
# CONFIG
# ============================================================

DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql://postgres:postgres@localhost:5432/treasury_engine",
)

CONFIG_FILE = Path(__file__).resolve().with_name("config.py")

if CONFIG_FILE.is_file():
    spec = importlib.util.spec_from_file_location(
        "local_config",
        CONFIG_FILE,
    )
    local_config = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(local_config)
    CONFIG_FRED_API_KEY = getattr(local_config, "FRED_API_KEY", None)
else:
    CONFIG_FRED_API_KEY = None

FRED_API_KEY = os.getenv(
    "FRED_API_KEY",
    CONFIG_FRED_API_KEY or "YOUR_FRED_API_KEY",
)

FRED_SERIES = {
    "1M": "DGS1MO",
    "3M": "DGS3MO",
    "6M": "DGS6MO",
    "1Y": "DGS1",
    "2Y": "DGS2",
    "5Y": "DGS5",
    "10Y": "DGS10",
    "30Y": "DGS30",
}


# ============================================================
# DATABASE SETUP
# ============================================================

Base = declarative_base()

engine = create_engine(DATABASE_URL, pool_pre_ping=True)
SessionLocal = sessionmaker(bind=engine)


# ============================================================
# DATABASE MODELS
# ============================================================

class TreasuryYield(Base):
    __tablename__ = "treasury_yields"

    id = Column(Integer, primary_key=True, index=True)
    observation_date = Column(Date, nullable=False)
    maturity = Column(String(10), nullable=False)
    yield_value = Column(Float, nullable=False)
    source = Column(String(50), nullable=False, default="FRED")
    created_at = Column(DateTime, default=datetime.utcnow)

    __table_args__ = (
        UniqueConstraint(
            "observation_date",
            "maturity",
            name="uq_observation_maturity",
        ),
    )


class DerivedMetric(Base):
    __tablename__ = "derived_metrics"

    id = Column(Integer, primary_key=True, index=True)
    observation_date = Column(Date, nullable=False)
    metric_name = Column(String(50), nullable=False)
    metric_value = Column(Float, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)


# ============================================================
# PYDANTIC RESPONSE MODELS
# ============================================================

class TreasuryResponse(BaseModel):
    maturity: str
    observation_date: str
    yield_value: float


class SpreadResponse(BaseModel):
    spread_name: str
    value: float


# ============================================================
# FASTAPI APP
# ============================================================

app = FastAPI(
    title="Treasury Yield Engine",
    version="1.0.0",
    description="Production-ready Treasury analytics backend",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["*"],
)


# ============================================================
# DATABASE INIT
# ============================================================

@app.on_event("startup")
def startup():
    try:
        Base.metadata.create_all(bind=engine)
    except OperationalError as exc:
        print(f"Database startup warning: {exc}")


# ============================================================
# DATA INGESTION
# ============================================================

def is_data_upto_date(
    db,
    reference_date: date | None = None,
) -> bool:
    """
    Return True when the latest stored treasury records match the
    latest available reference date from the source.
    """
    latest = (
        db.query(TreasuryYield)
        .order_by(TreasuryYield.observation_date.desc())
        .first()
    )

    if not latest:
        return False

    if reference_date is None:
        return True

    return latest.observation_date >= reference_date


async def get_latest_source_date() -> date | None:
    """
    Return the latest observation date available from the configured
    Treasury source.
    """
    latest_date = None

    for fred_series in FRED_SERIES.values():
        payload = await fetch_fred_series(fred_series)
        observations = payload.get("observations", [])

        for item in observations:
            value = item.get("value")
            if value == ".":
                continue

            item_date = datetime.strptime(item["date"], "%Y-%m-%d").date()
            if latest_date is None or item_date > latest_date:
                latest_date = item_date
            break

    return latest_date


async def fetch_fred_series(series_id: str):
    """
    Fetch Treasury data from FRED.
    """

    url = "https://api.stlouisfed.org/fred/series/observations"

    params = {
        "series_id": series_id,
        "api_key": FRED_API_KEY,
        "file_type": "json",
        "sort_order": "desc",
    }

    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.get(url, params=params)
        response.raise_for_status()

    return response.json()


async def ingest_all_treasury_data():
    """
    Fetch all configured Treasury maturities.
    """

    db = SessionLocal()

    try:
        for maturity, fred_series in FRED_SERIES.items():
            payload = await fetch_fred_series(fred_series)

            observations = payload.get("observations", [])

            for item in observations:
                value = item.get("value")

                if value == ".":
                    continue

                row = TreasuryYield(
                    observation_date=datetime.strptime(
                        item["date"],
                        "%Y-%m-%d",
                    ).date(),
                    maturity=maturity,
                    yield_value=float(value),
                    source="FRED",
                )

                exists = (
                    db.query(TreasuryYield)
                    .filter(
                        TreasuryYield.observation_date
                        == row.observation_date,
                        TreasuryYield.maturity == row.maturity,
                    )
                    .first()
                )

                if not exists:
                    db.add(row)

        db.commit()

    finally:
        db.close()


# ============================================================
# ANALYTICS
# ============================================================


def compute_2s10s(two_year: float, ten_year: float):
    return round(ten_year - two_year, 4)



def compute_zscore(values: List[float], latest: float):
    if len(values) < 2:
        return 0

    mean = statistics.mean(values)
    std_dev = statistics.stdev(values)

    if std_dev == 0:
        return 0

    return round((latest - mean) / std_dev, 4)


# ============================================================
# API ENDPOINTS
# ============================================================

@app.get("/")
def healthcheck():
    return {
        "status": "running",
        "service": "treasury-data-engine",
    }


@app.get("/dashboard")
def dashboard():
    dashboard_path = Path(__file__).resolve().with_name("treasury_dashboard.html")
    return FileResponse(dashboard_path)


@app.get("/api/rates/latest")
def latest_treasury_yields():
    db = SessionLocal()

    try:
        results = []

        for maturity in FRED_SERIES.keys():
            latest = (
                db.query(TreasuryYield)
                .filter(TreasuryYield.maturity == maturity)
                .order_by(TreasuryYield.observation_date.desc())
                .first()
            )

            if latest:
                results.append(
                    {
                        "maturity": latest.maturity,
                        "observation_date": str(latest.observation_date),
                        "yield_value": latest.yield_value,
                    }
                )

        return results

    finally:
        db.close()


@app.get("/api/rates/status")
async def rates_status():
    db = SessionLocal()

    try:
        source_latest = await get_latest_source_date()
        latest_record = (
            db.query(TreasuryYield)
            .order_by(TreasuryYield.observation_date.desc())
            .first()
        )

        latest_date = (
            latest_record.observation_date
            if latest_record
            else None
        )

        up_to_date = (
            latest_date is not None
            and source_latest is not None
            and latest_date >= source_latest
        )

        if not up_to_date:
            await ingest_all_treasury_data()

            latest_record = (
                db.query(TreasuryYield)
                .order_by(TreasuryYield.observation_date.desc())
                .first()
            )
            latest_date = (
                latest_record.observation_date
                if latest_record
                else None
            )
            up_to_date = (
                latest_date is not None
                and source_latest is not None
                and latest_date >= source_latest
            )

        return {
            "up_to_date": up_to_date,
            "latest_observation_date": (
                str(latest_date) if latest_date else None
            ),
            "source_latest_observation_date": (
                str(source_latest) if source_latest else None
            ),
            "source": "FRED",
        }

    finally:
        db.close()


@app.get("/treasury/spreads")
def treasury_spreads():
    db = SessionLocal()

    try:
        latest_2y = (
            db.query(TreasuryYield)
            .filter(TreasuryYield.maturity == "2Y")
            .order_by(TreasuryYield.observation_date.desc())
            .first()
        )

        latest_10y = (
            db.query(TreasuryYield)
            .filter(TreasuryYield.maturity == "10Y")
            .order_by(TreasuryYield.observation_date.desc())
            .first()
        )

        if not latest_2y or not latest_10y:
            return {
                "error": "Treasury data not loaded yet"
            }

        spread = compute_2s10s(
            latest_2y.yield_value,
            latest_10y.yield_value,
        )

        return SpreadResponse(
            spread_name="2s10s",
            value=spread,
        )

    finally:
        db.close()


@app.post("/ingest")
async def ingest_data():
    await ingest_all_treasury_data()

    return {
        "status": "success",
        "message": "Treasury data ingested successfully",
    }


@app.get("/analytics/zscore/{maturity}")
def zscore(maturity: str):
    db = SessionLocal()

    try:
        rows = (
            db.query(TreasuryYield)
            .filter(TreasuryYield.maturity == maturity.upper())
            .order_by(TreasuryYield.observation_date.asc())
            .all()
        )

        if not rows:
            return {
                "error": "No data found"
            }

        values = [r.yield_value for r in rows]

        latest = values[-1]

        score = compute_zscore(values, latest)

        return {
            "maturity": maturity.upper(),
            "latest": latest,
            "zscore": score,
        }

    finally:
        db.close()


# ============================================================
# LOCAL DEVELOPMENT ENTRYPOINT
# ============================================================

if __name__ == "__main__":
    import uvicorn

    def find_available_port(start_port: int = 8000, max_attempts: int = 20):
        for port in range(start_port, start_port + max_attempts):
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
                sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
                try:
                    sock.bind(("0.0.0.0", port))
                    return port
                except OSError:
                    continue
        return start_port

    port = int(os.getenv("PORT", find_available_port()))

    uvicorn.run(
        "treasury_data_engine:app",
        host="0.0.0.0",
        port=port,
        reload=True,
    )