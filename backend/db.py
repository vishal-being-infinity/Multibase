"""
Database connection handling for the backend.
Uses a read-only role for serving queries - schema changes and seeding
always go through DATABASE_URL directly via psql, never through this pool.
"""

import os

from dotenv import load_dotenv
from psycopg_pool import ConnectionPool

load_dotenv()

# read-only role - this pool can never modify data, even if app-level
# validation below has a bug
pool = ConnectionPool(conninfo=os.getenv("READONLY_DATABASE_URL"), min_size=1, max_size=5)

# keywords that indicate a write/destructive statement - belt-and-suspenders
# check in addition to the DB-level read-only role
BLOCKED_KEYWORDS = ["INSERT", "UPDATE", "DELETE", "DROP", "ALTER", "TRUNCATE", "GRANT", "REVOKE"]


# raised when a query fails our app-level safety check, before it even reaches postgres
class UnsafeQueryError(Exception):
    pass


# rejects anything that isn't a plain SELECT, before it ever reaches the DB
def validate_readonly(sql: str) -> None:
    normalized = sql.strip().upper()
    if not normalized.startswith("SELECT"):
        raise UnsafeQueryError("only SELECT queries are allowed")
    if any(keyword in normalized for keyword in BLOCKED_KEYWORDS):
        raise UnsafeQueryError("query contains a disallowed keyword")


# runs a read-only SQL query and returns rows as a list of dicts
def run_query(sql: str, params: tuple = ()) -> list[dict]:
    validate_readonly(sql)
    with pool.connection() as conn:
        with conn.cursor() as cur:
            cur.execute(sql, params)
            columns = [desc[0] for desc in cur.description]
            return [dict(zip(columns, row)) for row in cur.fetchall()]