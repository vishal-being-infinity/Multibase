"""
Neo4j connection handling for the backend. Aura's Free tier doesn't
support creating a read-only Viewer role, so safety here is app-level
only - a regex check blocking write clauses before any query runs.
"""

import os
import re

from dotenv import load_dotenv
from neo4j import GraphDatabase

load_dotenv()

_driver = GraphDatabase.driver(
    os.getenv("NEO4J_URI"),
    auth=(os.getenv("NEO4J_USER"), os.getenv("NEO4J_PASSWORD")),
)

# any of these appearing as a whole word anywhere in the query is rejected -
# Cypher write clauses can appear mid-query, not just at the start like SQL
WRITE_CLAUSES = re.compile(
    r"\b(CREATE|MERGE|DELETE|DETACH|SET|REMOVE|DROP|LOAD\s+CSV)\b",
    re.IGNORECASE,
)


class UnsafeCypherError(Exception):
    pass


def validate_readonly(cypher: str) -> None:
    if WRITE_CLAUSES.search(cypher):
        raise UnsafeCypherError("query contains a disallowed write clause")


# runs a read-only Cypher query and returns a list of plain dicts
def run_cypher(cypher: str, params: dict = None) -> list[dict]:
    validate_readonly(cypher)
    with _driver.session() as session:
        result = session.run(cypher, params or {})
        return [dict(record) for record in result]