# Design decisions

## Postgres for v1 (not Mongo/Neo4j yet)
Contest → problem → submission data is inherently relational (foreign keys,
joins). Starting with one well-understood DB keeps the NL→query layer simple;
Mongo/Neo4j get added later for specific use cases (raw logs, relationship
queries) once the core pipeline works.
Trade-off: less flexible for unstructured data (e.g. raw submitted code) until
Mongo is added.

## LLM provider abstraction (Claude or Gemini, configurable)
A thin `LLMProvider` interface means swapping models is a config change, not
a rewrite, and lets us A/B cost/quality later.
Trade-off: slight upfront complexity vs. hardcoding one provider.

## Docker Postgres on a non-default port (5433)
Local machine already had a Homebrew Postgres bound to 5432. Rather than
touch that install, Docker's container maps to 5433 instead.
Trade-off: anyone cloning this repo needs to check their own 5432 isn't
occupied, or adjust DATABASE_URL accordingly. Documented in .env.example.

## Forced tool use for LLM structured output
Rather than prompting Claude to "return JSON" and hoping it complies, we
define a tool whose schema IS the response shape we want, then force
Claude to call it. Guarantees valid, parseable output every time.
Trade-off: slightly more setup than a plain prompt, but eliminates a whole
class of parsing failures.

## Two-layer safety: app-level validation + DB-level read-only role
LLM-generated SQL runs through a keyword/prefix check in db.py before
execution, AND the DB connection itself uses a Postgres role with only
SELECT granted. Neither layer alone is trusted - if the app check has a
bug or gets bypassed, the DB role still blocks writes.
Verified independently: DELETE was rejected both by the app check and,
separately, by Postgres directly when tested as nl2sql_readonly.

## Stateless multi-turn via client-supplied history
Rather than storing conversation state server-side (sessions, Redis, etc.),
the client resends the full conversation each time as a `history` array.
Keeps the backend simple and horizontally scalable from day one.
Trade-off: slightly more payload per request, and the client must track
history correctly - acceptable for v1, revisit if this becomes a real API
with many concurrent users.

Yes, quite a bit accumulated — let's catch up the docs properly since we went through some real debugging that's worth remembering.

Update DECISIONS.md — add these entries:

markdown
## Project renamed nl2sql-project -> Multibase
Reflects the actual direction: Postgres now, Mongo and Neo4j later. The old
name only described the first phase.

## Schema + read-only role live in db/init/, not manual commands
Early on, the read-only Postgres role was created by hand via psql. Every
`docker compose down -v` silently deleted it, causing repeated
"password authentication failed" errors that took real debugging time to
trace back to a wiped volume.
Fixed by moving both schema.sql and the role creation into db/init/*.sql,
which Postgres runs automatically on first boot of a fresh volume. Schema
and permissions are now self-healing; only seed data needs a manual rerun
after a volume wipe (`python3 scripts/seed.py`).

## Renaming the project folder requires recreating the venv
Python virtual environments bake in absolute paths at creation time.
Renaming nl2sql-project -> Multibase left the venv silently pointing at
the old path, causing confusing "module not found" and stale-code errors
that looked unrelated to the actual cause.
Fixed by deleting and recreating venv/ inside the new folder. Documented
here so future renames don't cost another debugging session.

## Chart type auto-detected from result shape
Rather than always showing a bar chart, the frontend inspects the query
result: a date-like label column -> line chart, few rows -> pie, long
labels or many rows -> horizontal bar, otherwise -> vertical bar. Falls
back to a plain table when the shape doesn't fit any chart (e.g. 2+
numeric columns). Every chart gets a legend (swatch + label + value).

## SQL panel is per-card, not a global drawer
Each result card has its own collapsible query panel that opens beside
its own output, sized to match. Kept as a single persistent DOM node
that toggles a CSS class (rather than swapping between two different
elements) after an early version's collapse button silently stopped
responding to clicks.

## Backend and frontend containerized, not just Postgres
Originally only Postgres ran in Docker; backend and frontend were started
manually in separate terminals with a venv that had to be activated each
time. Now `docker-compose.yml` runs all three services, with a Makefile
(`make up`, `make down`, `make reset`, `make seed`, `make logs`) wrapping
the common commands.
This also doubles as the deployment artifact - the same containers that
run locally are what would run in production - and gives a template for
adding mongo/neo4j services the same way.
Trade-off: `.env` had to be restructured (individual POSTGRES_* vars
instead of one DATABASE_URL) so docker-compose could build connection
strings using the internal service name (`postgres`) rather than
`localhost`, since containers reach each other by service name on the
docker network, not localhost.

## Known simplification: read-only role password isn't templated
db/init/01-readonly-role.sql hardcodes the read-only role's password
rather than reading it from READONLY_PASSWORD in .env, since Postgres
doesn't template init SQL files with env vars. Fine for local dev; needs
proper secret handling before real deployment.

## Retry Claude API calls on 529 (overloaded), not other errors
Anthropic's API occasionally returns 529 during high demand, which is
transient and worth a short retry (2 attempts, exponential backoff).
Other errors (bad key, invalid request) fail immediately rather than
wasting time retrying something that won't self-resolve.
Correct exception is `anthropic.InternalServerError` with
`status_code == 529` - not `OverloadedError`, which isn't an importable
exception in the SDK despite appearing in some naming.

## Conversation history persists client-side with rolling 24h expiry
Chat history is saved to [localStorage/wherever you land], with a rolling
24-hour window that resets on each new message rather than a fixed expiry
from first message. A manual "clear history" button lets the user reset
early.
Trade-off: [whatever you actually run into - e.g. history lost if
localStorage is cleared, or doesn't sync across devices/browsers].