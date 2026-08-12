# MULTIBASE — Competitive Programming Analytics

Ask questions in plain English about students, contests, problems, and submissions.
Claude/Gemini (configurable) converts your question to SQL, asks for clarification
if it's ambiguous, and returns results as a table, chart, or summary.

Currently Postgres-backed; MongoDB and Neo4j are planned next (see DECISIONS.md).

## Architecture

See `ARCHITECTURE.md` for the full diagram and data flow.

## Quick start

```bash
make up      # builds and starts postgres + backend + frontend
make seed    # populates sample data (needed once, or after a volume reset)
```

Then open http://localhost:5173. Backend runs at http://localhost:8000.

Other commands:
```bash
make logs    # tail all service logs
make down    # stop everything, keep data
make reset   # wipe the database and start fresh, then reseed
```

## Backend

FastAPI app in `backend/`, containerized alongside Postgres and the frontend
(see `docker-compose.yml`). No manual venv/uvicorn steps needed - `make up`
handles it.

- `GET /health` - confirms API and DB connectivity
- `POST /query` - runs raw SQL directly (scaffold only, no LLM - see DECISIONS.md)
- `POST /ask` - takes a question + optional conversation history, returns either
  results or a clarifying question if the request is ambiguous. Client resends
  history on follow-ups (see DECISIONS.md).

LLM provider is configurable via `LLM_PROVIDER` in `.env` (currently `claude`;
built behind a provider interface so Gemini can be added later without
touching the rest of the app).

## Frontend

React + Vite app in `frontend/`. A judge-terminal-styled UI: every answer gets
a verdict badge (AC/PENDING/CE), a collapsible query panel next to its output,
and a chart auto-picked from the result shape (line for trends, pie for small
breakdowns, horizontal/vertical bar otherwise) with a legend, or a table when
no chart fits.
Conversation history persists across page reloads (rolling 24h window,
clearable via the "clear history" button).

## Safety

Queries run through app-level validation (SELECT-only, blocked keywords)
and a DB-level read-only Postgres role. Both are tested independently -
see DECISIONS.md.

## Results

Seeded dataset: 300 students, 40 contests, 320 problems, ~12k submissions
across 3 platforms (Codeforces, LeetCode, CodeChef). Regenerates with
different (but similarly realistic) numbers each time `make seed` runs.

## Design decisions

See `DECISIONS.md` for why Postgres-first, the LLM provider abstraction,
containerizing the whole stack, and other key choices.

## Local dev gotchas

- **Running scripts outside Docker** (e.g. one-off debugging) still needs
  `source venv/bin/activate` from the project root first. A missing
  `(venv)` prefix in your prompt means commands will fail with "module not
  found" or "command not found".
- **`docker compose down` vs `down -v`**: plain `down` keeps your data.
  `down -v` wipes the Postgres volume entirely - schema and the read-only
  role recreate themselves automatically on next `up -d` (see
  DECISIONS.md), but you'll need to rerun `make seed`.
- **Renaming the project folder**: delete and recreate `venv/` afterward -
  it bakes in absolute paths and won't follow the rename on its own.
- **Editing code across multiple files for one change**: double-check each
  file's full import list after edits, not just the lines that changed - a
  partial edit that only shows a diff can silently drop an existing import.