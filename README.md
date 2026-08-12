# MULTIBASE — Competitive Programming Analytics

Ask questions in plain English about students, contests, problems, and submissions.
Claude/Gemini (configurable, with automatic fallback) converts your question into
the right query for the right database, asks for clarification if it's ambiguous,
and returns results as a table, chart, document view, or summary.

## Architecture

See `ARCHITECTURE.md` for the full diagram and data flow.


## Databases

- **Postgres** (Neon) - students, contests, problems, submissions
- **MongoDB** (Atlas) - editorials + discussion threads, full problem
  statements, submitted code
- **Neo4j** (AuraDB) - mentorship, follows, rivalries between students,
  and problem similarity

All three are managed cloud services - no local database containers.

## Quick start

```bash
make up        # builds and starts postgres + backend + frontend, auto-seeds
               # any database that's currently empty
```

Then open http://localhost:5173. Backend runs at http://localhost:8000.

Other commands:
```bash
make logs           # tail all service logs
make down            # stop everything, keep data
make reset           # wipe local Postgres volume, start fresh, reseed
make seed-postgres   # force-reseed Postgres with fresh random data
make seed-mongo      # force-reseed Mongo
make seed-neo4j      # force-reseed Neo4j
make seed-all        # all three
```

## Backend

FastAPI app in `backend/`, containerized alongside Postgres and the frontend
(see `docker-compose.yml`). No manual venv/uvicorn steps needed - `make up`
handles it.

- `GET /health` - confirms API and DB connectivity
- `GET /schema` - structure + live record counts for all three databases
- `POST /query` - runs raw SQL directly (scaffold only, no LLM - see DECISIONS.md)
- `POST /ask` - takes a question + optional conversation history. Routes to
  Postgres, MongoDB, or Neo4j automatically (one LLM call picks the database and
  generates the matching query - SQL, a Mongo filter/pipeline, or Cypher), or
  returns a clarifying question if ambiguous.

LLM provider order is configurable via `LLM_PROVIDER_ORDER` in `.env`
(e.g. `claude,gemini`) - tries each in order, falling through on failure. Built
behind a provider interface (`LLMProvider`) so adding another model is a new
provider class, not a rewrite.

## Frontend

React + Vite app in `frontend/`. A judge-terminal-styled UI:
- Every answer gets a verdict badge (AC/PENDING/CE) and a source tag showing
  which database answered it (postgres/mongodb/neo4j, color-coded)
- Postgres results render as a table or an auto-picked chart (line/pie/bar,
  based on result shape) with a legend
- Mongo results render as document cards (nested fields shown properly, not
  flattened into table rows)
- A collapsible query panel sits beside each result, showing the generated
  SQL/Mongo query/Cypher
- Dark/light theme toggle, persisted
- Conversation history persists across page reloads (rolling 24h window,
  clearable via the "clear history" button)
- "View schema" shows structure + live seeded counts for all three databases,
  tabbed by source

## Safety

- **Postgres**: app-level query validation (SELECT-only, blocked keywords) +
  DB-level read-only role. Both verified independently.
- **MongoDB**: only `find`/`aggregate` are ever callable (no raw query strings),
  plus a DB-level read-only Atlas user. Both verified independently.
- **Neo4j**: app-level Cypher validation only (regex-blocks write clauses
  anywhere in the query text) - Aura's Free tier doesn't support a DB-level
  read-only role. Known single-layer gap, documented in DECISIONS.md.

## Design decisions

See `DECISIONS.md` for the full history - why Postgres-first then Mongo/Neo4j,
the LLM provider abstraction and fallback, containerizing the whole stack, the
routing design, and the debugging lessons picked up along the way.

## Local dev gotchas

- **Running scripts outside Docker** (e.g. one-off debugging) still needs
  `source venv/bin/activate` from the project root first.
- **`.env` changes need a container recreate**: `docker compose up -d
  --force-recreate <service>` - editing `.env` alone has no effect on an
  already-running container.
- **`requirements.txt` changes need a rebuild**: `docker compose up -d --build
  <service>`.
- **Renaming the project folder**: delete and recreate `venv/` afterward - it
  bakes in absolute paths and won't follow the rename on its own.
- **After any manual multi-line edit to a Python file**: run `python3 -m
  py_compile <file>` before rebuilding - catches indentation/syntax errors in
  under a second instead of chasing a traceback through several rebuild cycles.
- **Removing a service from `docker-compose.yml`**: doesn't stop its
  already-running container. Manually `docker rm -f <container>` and
  `docker network rm <network>` if you hit "Resource is still in use."