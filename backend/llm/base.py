"""
Abstract interface for LLM providers. Any provider (Claude, Gemini, etc.)
must implement process_question so the rest of the app never needs to
know which model is actually running.
"""

from abc import ABC, abstractmethod
from typing import TypedDict


# one exchange in the conversation - either the user or the assistant
class Turn(TypedDict):
    role: str  # "user" or "assistant"
    content: str


# shape returned by any provider - either a clarifying question or a SQL query
class LLMResponse(TypedDict):
    status: str  # "clear" or "ambiguous"
    sql: str | None
    clarifying_question: str | None


class LLMProvider(ABC):
    # takes the full conversation so far + schema description, returns either sql or a clarifying question
    @abstractmethod
    def process_question(self, history: list[Turn], schema_context: str) -> LLMResponse:
        ...