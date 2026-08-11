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