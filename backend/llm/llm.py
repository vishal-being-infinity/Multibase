"""
Claude implementation of LLMProvider. Uses forced tool use so the response
is always valid structured data - no JSON parsing guesswork.
"""

import os

from anthropic import Anthropic

from .base import LLMProvider, LLMResponse

# single tool whose schema IS our desired response shape - forcing Claude
# to call it guarantees we get back exactly this structure
RESPONSE_TOOL = {
    "name": "process_question",
    "description": "Return either a SQL query for a clear question, or a clarifying question for an ambiguous one.",
    "input_schema": {
        "type": "object",
        "properties": {
            "status": {
                "type": "string",
                "enum": ["clear", "ambiguous"],
                "description": "clear if the question can be answered with one unambiguous SQL query",
            },
            "sql": {
                "type": "string",
                "description": "read-only SELECT query, only set when status is clear",
            },
            "clarifying_question": {
                "type": "string",
                "description": "a short question to ask the user, only set when status is ambiguous",
            },
        },
        "required": ["status"],
    },
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


class ClaudeProvider(LLMProvider):
    def __init__(self):
        self.client = Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))
        self.model = "claude-sonnet-5"

    # sends the question + schema to Claude, forces the process_question tool, returns parsed result
    def process_question(self, question: str, schema_context: str) -> LLMResponse:
        message = self.client.messages.create(
            model=self.model,
            max_tokens=1024,
            system=SYSTEM_PROMPT,
            tools=[RESPONSE_TOOL],
            tool_choice={"type": "tool", "name": "process_question"},
            messages=[
                {"role": "user", "content": f"Schema:\n{schema_context}\n\nQuestion: {question}"}
            ],
        )

        # forced tool use means the tool_use block is guaranteed to be present
        tool_block = next(b for b in message.content if b.type == "tool_use")
        result = tool_block.input

        return LLMResponse(
            status=result.get("status"),
            sql=result.get("sql"),
            clarifying_question=result.get("clarifying_question"),
        )