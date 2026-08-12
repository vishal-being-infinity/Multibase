"""
Abstract interface for LLM providers. Any provider (Claude, Gemini, etc.)
must implement process_question so the rest of the app never needs to
know which model is actually running.
"""

from abc import ABC, abstractmethod
from typing import TypedDict


class Turn(TypedDict):
    role: str
    content: str


# shape returned by any provider - which database (if any) to query, and how
class LLMResponse(TypedDict):
    status: str                # "clear" or "ambiguous"
    target_db: str | None      # "postgres" or "mongo", only set when status is "clear"
    sql: str | None            # set when target_db is "postgres"
    mongo_query: dict | None   # set when target_db is "mongo" - {collection, operation, filter/pipeline, limit}
    clarifying_question: str | None
    cypher: str | None         # set when target_db is "neo4j"


class LLMProvider(ABC):
    @abstractmethod
    def process_question(self, history: list[Turn], schema_context: str, mongo_schema_context: str = "") -> LLMResponse:
        ...