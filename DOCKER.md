# ClaimGuard — Docker Deployment Guide

## Prerequisites

- [Docker Desktop](https://www.docker.com/products/docker-desktop/) installed and running
- No other services on ports **8000** or **8501**

## Quick Start

```bash
# 1. Build images
docker compose build

# 2. Start both services
docker compose up -d

# 3. Verify
docker compose ps
```

## Service URLs

| Service | URL |
|---------|-----|
| **API** | [http://localhost:8000](http://localhost:8000) |
| **API Health** | [http://localhost:8000/health](http://localhost:8000/health) |
| **Swagger Docs** | [http://localhost:8000/docs](http://localhost:8000/docs) |
| **ReDoc** | [http://localhost:8000/redoc](http://localhost:8000/redoc) |
| **Streamlit UI** | [http://localhost:8501](http://localhost:8501) |

## Common Commands

```bash
# View running containers
docker compose ps

# View live logs (both services)
docker compose logs -f

# View logs for a single service
docker compose logs -f api
docker compose logs -f ui

# Stop all services
docker compose down

# Rebuild after code changes
docker compose build --no-cache
docker compose up -d
```

## Environment Variables

Copy the example file and fill in your values:

```bash
cp .env.example .env
```

| Variable | Required | Description |
|----------|----------|-------------|
| `GROQ_API_KEY` | No | Groq API key for LLM extraction. Falls back to regex if unset. |
| `CLAIMGUARD_ALLOWED_ORIGINS` | No | Comma-separated CORS origins. Defaults to localhost. |

> **⚠️ WARNING:** Never commit your `.env` file. It is excluded by `.gitignore`.

## Architecture

```
docker compose up -d
        │
        ├── claimguard-api (FastAPI)
        │     Port: 8000
        │     Command: uvicorn api.main:app --host 0.0.0.0 --port 8000
        │     Healthcheck: GET /health
        │
        └── claimguard-ui (Streamlit)
              Port: 8501
              Command: streamlit run app.py --server.address 0.0.0.0 --server.port 8501
```

Both containers share the same image and the same deterministic rule engine.

## Smoke Test

After starting:

```bash
# Health check
curl http://localhost:8000/health

# Rule listing
curl http://localhost:8000/rules

# Audit test (Demo A — should return PASS)
curl -X POST http://localhost:8000/audit \
  -H "Content-Type: application/json" \
  -d '{
    "narrative": "Achieved a 2.59% reduction in Scope 1 & 2 emissions in FY24 vs FY23.",
    "metrics": [
      {"metric_id": "MTR-TOTAL", "category": "Emissions", "metric_name": "Total Scope 1 & 2 Emissions", "unit": "MT CO2e", "fy23_value": 10500.0, "fy24_value": 10228.05}
    ]
  }'
```
