# Farm Platform

Digital field intelligence and agricultural record system.

## Stack

- Mobile: React Native + Expo
- Web: Next.js
- API: FastAPI
- Python management: uv
- Database: PostgreSQL + PostGIS
- Satellite processing: Python
- Maps: MapLibre
- Infrastructure: Google Cloud

## Run API

```bash
cd services/api
uv sync
uv run uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
