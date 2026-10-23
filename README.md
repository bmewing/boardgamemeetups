# Board Game Group

Organize board game meetups: track who's coming, pool everyone's collections, and get game
recommendations based on player count, wishlists, and the group's mood. See [PLAN.md](PLAN.md)
for the roadmap.

- `backend/` — FastAPI, SQLAlchemy 2 (async), Alembic, Postgres
- `frontend/` — React, Vite, TypeScript, Mantine, TanStack Query

## Prerequisites

- [uv](https://docs.astral.sh/uv/) (installs Python 3.14 for you)
- Node.js 24+
- Docker (for the local Postgres)

## Running locally

Start Postgres:

```bash
docker compose up -d
```

Backend (http://localhost:8000, docs at `/api/docs`):

```bash
cd backend
cp .env.example .env
uv sync
uv run alembic upgrade head
uv run fastapi dev app/main.py
```

Frontend (http://localhost:5173; `/api` is proxied to the backend):

```bash
cd frontend
npm install
npm run dev
```

## Checks

Backend, from `backend/`:

```bash
uv run ruff format --check . && uv run ruff check . && uv run mypy && uv run pytest
```

The tests need the docker-compose Postgres running.

Frontend, from `frontend/`:

```bash
npm run format:check && npm run lint && npm run typecheck && npm test
```

## API types

The frontend's API client is typed from the backend's OpenAPI schema. After changing an
endpoint, regenerate it from `frontend/` and commit the result:

```bash
npm run gen:api
```

## Migrations

```bash
cd backend
uv run alembic revision --autogenerate -m "describe the change"
uv run alembic upgrade head
```

New models must be imported in `app/models/__init__.py` for autogenerate to see them.
