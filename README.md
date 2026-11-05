# Board Game Group

Organize board game meetups: track who's coming, pool everyone's collections, and get game
recommendations based on player count, wishlists, and the group's mood. See [PLAN.md](PLAN.md)
for the roadmap.

- `backend/` — FastAPI, SQLAlchemy 2 (async), Alembic, Postgres
- `frontend/` — React, Vite, TypeScript, Mantine, TanStack Query
- `functions/` — packages the backend as a DigitalOcean function for deployment

## Prerequisites

- [uv](https://docs.astral.sh/uv/) (installs Python 3.14 for you)
- Node.js 24+
- PostgreSQL 16+ running locally

## Running locally

Create the local role and database once, as the `postgres` superuser:

```bash
psql -U postgres -c "CREATE ROLE boardgame LOGIN PASSWORD 'boardgame'" -c "CREATE DATABASE boardgamegroup OWNER boardgame"
```

Different credentials work too; just put them in `backend/.env`.

Sign-in uses [Kinde](https://kinde.com). You need a Kinde **React** application (callback and
logout URLs `http://localhost:5173`) and a Kinde **API** whose audience the app is enabled for.
Put the domain and audience in `backend/.env`, and the domain, client ID and audience in
`frontend/.env.local`. None of these values are secret.

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
cp .env.example .env.local
npm install
npm run dev
```

## Game catalog

Game data comes from the [BoardGameGeek XML API](https://boardgamegeek.com/using_the_xml_api).
Put your BGG application token in `backend/.env` as `BGG_API_TOKEN`. The backend caches what it
fetches and spaces its BGG requests about five seconds apart, as BGG asks.

Optionally, preload every game's name and rank so search works locally without asking BGG:
download the ranks CSV while logged in to BGG at https://boardgamegeek.com/data_dumps/bg_ranks,
then from `backend/`:

```bash
uv run python -m app.import_bgg_ranks path/to/boardgames_ranks.zip
```

## Admins

Admins get an **Admin** item in the account menu, leading to `/admin`: site-wide stats, and
banning, deleting or promoting accounts. Make the first admin from `backend/` (they must have
signed in once); after that, admins can promote others from the portal:

```bash
uv run python -m app.admins grant you@example.com
```

`revoke EMAIL` and `list` work too. Add `--env-file .env.production` after `uv run` for
production.

## Checks

Backend, from `backend/`:

```bash
uv run ruff format --check . && uv run ruff check . && uv run mypy && uv run pytest
```

The tests need the local Postgres database from above. They run in their own `pytest`
schema, rebuilt empty on each run, so they never read or change your dev data.

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

## Deployment

Production runs on DigitalOcean App Platform (`.do/app.yaml`): the frontend as a static site
and the whole API as one DigitalOcean function, `core/app`, reached at `/api/core/app/...`.
`backend/app/serverless.py` adapts function requests to the FastAPI app, so the code and
tests are the same as in local development.

- The function runs Python 3.13, the newest DigitalOcean offers; keep the backend on 3.13.
- The function runs a committed copy of the backend in `functions/lib/app` (a remote build
  only receives `functions/`, so it can't copy `backend/` itself). After changing
  `backend/app`, refresh the copy (CI fails if it's stale):

  ```bash
  bash functions/sync_backend.sh
  ```

- The function's `build.sh` installs `functions/packages/core/app/requirements.txt` in
  DigitalOcean's Python 3.13 container. After changing backend dependencies, regenerate it
  from `backend/` (CI fails if it's out of date):

  ```bash
  uv export --no-default-groups --no-hashes --no-emit-project --no-header --format requirements-txt -o ../functions/packages/core/app/requirements.txt
  ```

- Functions-only apps have no pre-deploy step, so run migrations against the production
  database yourself before deploying code that needs them. Production settings live in the
  gitignored `backend/.env.production`; from `backend/`:

  ```bash
  uv run --env-file .env.production alembic upgrade head
  uv run --env-file .env.production python -m app.import_bgg_ranks path/to/boardgames_ranks.zip
  ```

- A staging database (a second Supabase project, `boardgamemeetups-staging`) is there to try
  migrations on first. Its settings are in the gitignored `backend/.env.staging`, laid out like
  `.env.production` (including `SERVERLESS=true`, which the pooler needs):

  ```bash
  uv run --env-file .env.staging alembic upgrade head
  ```
- `DATABASE_URL` in production is Supabase's transaction pooler; `SERVERLESS=true` (set in
  `functions/project.yml`) turns off connection pooling and prepared-statement caching to suit it.
