# Treasury Data Engine

This project provides a FastAPI backend that stores Treasury yield data in PostgreSQL and serves a simple dashboard page.

## Requirements

- Python 3.11+
- PostgreSQL running locally (or a reachable database URL)
- A FRED API key set in your environment variables

## Environment setup

Set the API key before running the server:

```bash
export FRED_API_KEY=your_fred_api_key
```

If you want to override the database connection, you can also set:

```bash
export DATABASE_URL=postgresql://postgres:postgres@localhost:5432/treasury_engine
```

## Install dependencies

```bash
pip install -r requirements.txt
```

## Run the server

```bash
uvicorn treasury_data_engine:app --reload
```

Then open:

- http://127.0.0.1:8000/dashboard

## API endpoints

- `GET /api/rates/status`
- `GET /api/rates/latest`
- `POST /ingest`
