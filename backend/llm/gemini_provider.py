"""
Gemini implementation of LLMProvider. Uses response_schema (Gemini's
structured-output mode) so the response shape is guaranteed, same
guarantee Claude gets from forced tool use.
"""

import os

from google import genai
from google.genai import types
from google.genai.errors import APIError

from .base import LLMProvider, LLMResponse

RESPONSE_SCHEMA = {
    "type": "OBJECT",
    "properties": {
        "status": {"type": "STRING", "enum": ["clear", "ambiguous"]},
        "sql": {"type": "STRING"},
        "clarifying_question": {"type": "STRING"},
    },
    "required": ["status"],
}

SYSTEM_PROMPT = """You convert natural language questions into PostgreSQL SELECT queries
for a competitive programming analytics database.

Rules:
- Only generate read-only SELECT queries. Never INSERT, UPDATE, DELETE, or DROP.
- If the question is genuinely ambiguous (e.g. "top students" without saying by what
  metric, or missing a time range that matters), set status to "ambiguous" and ask ONE
  short, specific clarifying question.
- If the question is answerable as-is, set status to "clear" and write the SQL.
- Always use the exact table and column names given in the schema."""


class GeminiProvider(LLMProvider):
    def __init__(self):
        self.client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))
        self.model = "gemini-2.5-flash"

    # sends the conversation history + schema to Gemini, forces schema-conformant JSON output
    def process_question(self, history: list, schema_context: str) -> LLMResponse:
        # gemini has no separate "history" concept for a single call - fold it into one prompt
        conversation = "\n".join(f"{turn['role']}: {turn['content']}" for turn in history)
        prompt = f"Schema:\n{schema_context}\n\nConversation:\n{conversation}"

        response = self.client.models.generate_content(
            model=self.model,
            contents=prompt,
            config=types.GenerateContentConfig(
                system_instruction=SYSTEM_PROMPT,
                response_mime_type="application/json",
                response_schema=RESPONSE_SCHEMA,
            ),
        )

        import json
        result = json.loads(response.text)

        return LLMResponse(
            status=result.get("status"),
            sql=result.get("sql"),
            clarifying_question=result.get("clarifying_question"),
        )