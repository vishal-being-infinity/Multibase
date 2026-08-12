"""
Pydantic models for request/response shapes across all endpoints.
Kept separate from main.py so route logic and data contracts don't mix -
also gives FastAPI's auto-generated docs (/docs, /redoc) clean, reusable
schema definitions instead of inline classes scattered through the routes.
"""

from typing import Optional

from pydantic import BaseModel, Field


# ---------- requests ----------

class QueryRequest(BaseModel):
    sql: str


class Turn(BaseModel):
    role: str
    content: str


class AskRequest(BaseModel):
    question: str
    history: list[Turn] = []


# ---------- responses ----------

class HealthResponse(BaseModel):
    status: str
    db: str


class QueryResponse(BaseModel):
    row_count: int
    rows: list[dict]


class AskResponse(BaseModel):
    status: str = Field(..., description="'ok', 'ambiguous', or 'error'")
    source: Optional[str] = Field(None, description="'postgres', 'mongo', or 'neo4j' - which database answered")
    sql: Optional[str] = Field(None, description="The generated query (SQL, Mongo shorthand, or Cypher)")
    row_count: Optional[int] = None
    rows: Optional[list[dict]] = None
    clarifying_question: Optional[str] = Field(None, description="Set when status is 'ambiguous'")


class SchemaColumn(BaseModel):
    name: str
    pk: Optional[bool] = None
    ref: Optional[str] = None
    note: Optional[str] = None


class SchemaTable(BaseModel):
    name: str
    columns: list[SchemaColumn]
    seed_count: Optional[int] = None


class SchemaResponse(BaseModel):
    postgres: dict
    mongo: dict
    neo4j: dict