# MULTIBASE — Competitive Programming Analytics

Ask questions in plain English about students, contests, problems, and submissions.
Claude/Gemini (configurable) converts your question to SQL, asks for clarification
if it's ambiguous, and returns results as a table, chart, or summary.

## Architecture

See `ARCHITECTURE.md` for the full diagram and data flow.

## Quick start

\`\`\`bash
docker compose up -d              # start Postgres
source venv/bin/activate
pip install -r requirements.txt
psql < db/schema.sql              # apply schema (or use the command in setup notes)
python scripts/seed.py            # populate sample data
\`\`\`


## Backend

FastAPI app in `backend/`. Run with:
\`\`\`bash
cd backend
uvicorn main:app --reload --port 8000
\`\`\`

- `GET /health` - confirms API and DB connectivity
- `POST /query` - runs raw SQL (temporary, no LLM yet - see DECISIONS.md)
- `POST /ask` - takes a plain-english question, returns either results or
  a clarifying question if the request is ambiguous.
- takes a question + optional conversation history, returns
either results or a clarifying question. Client resends history on
follow-ups (see DECISIONS.md).


## Safety

Queries run through app-level validation (SELECT-only, blocked keywords)
and a DB-level read-only Postgres role. Both are tested independently -
see DECISIONS.md.


## Results

Seeded dataset: 300 students, 40 contests, 320 problems, ~12.3k submissions
across 3 platforms (Codeforces, LeetCode, CodeChef).


## Design decisions

See `DECISIONS.md` for why Postgres-first, the LLM provider abstraction, and
other key choices.