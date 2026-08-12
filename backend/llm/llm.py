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

SYSTEM_PROMPT = """You answer questions about a competitive programming platform by
routing to the correct database and generating the right query, in one step.

Three databases are available:
- Postgres: structured data - students, contests, problems (metadata only), submissions (metadata only)
- MongoDB: flexible content - editorial writeups + comments, full problem statements
  (constraints, examples), and submitted code text
- Neo4j: relationships - mentorship, follows, rivalries between students, and problem similarity

Rules:
- Pick exactly ONE tool per question. Most questions need only one database.
- Only generate read-only operations. Never write/modify data.
- If the question uses a bare superlative or ranking term - "top", "best", "worst",
  "hardest", "easiest", "most active", etc. - with NO metric, timeframe, or
  qualifier attached (e.g. "top students", "worst problems", "best performers"),
  you MUST call ask_clarification and ask what metric to rank by. Do not guess
  a default metric for these.
- This does NOT apply when a metric or qualifier IS present (e.g. "top students
  by rating", "hardest problems by acceptance rate", "most active students this
  month") - these are answerable as-is, generate the query normally.
- If the question is ambiguous for other reasons (missing a time range that
  matters, unclear which database it needs), also call ask_clarification with
  ONE short, specific question.
- Always use the exact table/column names, collection/field names, or node/relationship
  names given in the schemas."""


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