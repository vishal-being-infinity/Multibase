"""
Claude implementation of LLMProvider. Uses forced tool use so the response
is always valid structured data - no JSON parsing guesswork. Claude picks
one of four tools per question: query_postgres, query_mongo, query_neo4j,
or ask_clarification, so routing and query generation happen in one call.
"""

import os
import random
import time

from anthropic import Anthropic, APIStatusError

from .base import LLMProvider, LLMResponse

TOOLS = [
    {
        "name": "query_postgres",
        "description": "Query the Postgres database for structured data: students, contests, problems (metadata), and submissions (metadata like verdict/runtime, not code).",
        "input_schema": {
            "type": "object",
            "properties": {
                "sql": {"type": "string", "description": "A read-only SELECT query."},
            },
            "required": ["sql"],
        },
    },
    {
        "name": "query_mongo",
        "description": "Query MongoDB for flexible/nested content: editorial writeups and discussion comments, full problem statements with constraints and examples, or submitted code text.",
        "input_schema": {
            "type": "object",
            "properties": {
                "collection": {
                    "type": "string",
                    "enum": ["editorials", "problem_statements", "submission_code"],
                },
                "operation": {"type": "string", "enum": ["find", "aggregate"]},
                "filter": {
                    "type": "object",
                    "description": "MongoDB filter document, used when operation is 'find'.",
                },
                "pipeline": {
                    "type": "array",
                    "description": "MongoDB aggregation pipeline stages, used when operation is 'aggregate'.",
                    "items": {"type": "object"},
                },
                "limit": {"type": "integer", "description": "Max documents to return, default 20."},
            },
            "required": ["collection", "operation"],
        },
    },
    {
        "name": "query_neo4j",
        "description": "Query the graph database for relationship/connection questions: mentorship, follows, rivalries between students, or problem similarity.",
        "input_schema": {
            "type": "object",
            "properties": {
                "cypher": {"type": "string", "description": "A read-only Cypher query (MATCH/RETURN, no writes)."},
            },
            "required": ["cypher"],
        },
    },
    {
        "name": "ask_clarification",
        "description": "Ask the user a clarifying question when the request is genuinely ambiguous.",
        "input_schema": {
            "type": "object",
            "properties": {
                "question": {"type": "string"},
            },
            "required": ["question"],
        },
    },
]

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
- If the question is genuinely ambiguous (e.g. missing a metric or unclear which
  database it needs), call ask_clarification with ONE short, specific question.
- Always use the exact table/column names, collection/field names, or node/relationship
  names given in the schemas."""


class ClaudeProvider(LLMProvider):
    def __init__(self):
        self.client = Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))
        self.model = "claude-sonnet-5"

    def process_question(self, history: list, schema_context: str, mongo_schema_context: str = "", neo4j_schema_context: str = "") -> LLMResponse:
        messages = [{"role": turn["role"], "content": turn["content"]} for turn in history]
        combined_schema = (
            f"Postgres schema:\n{schema_context}\n\n"
            f"MongoDB schema:\n{mongo_schema_context}\n\n"
            f"Neo4j schema:\n{neo4j_schema_context}"
        )
        messages[0]["content"] = f"{combined_schema}\n\n{messages[0]['content']}"

        last_error = None
        max_attempts = 5
        for attempt in range(max_attempts):
            try:
                message = self.client.messages.create(
                    model=self.model,
                    max_tokens=1024,
                    system=SYSTEM_PROMPT,
                    tools=TOOLS,
                    tool_choice={"type": "any"},
                    messages=messages,
                )
                tool_block = next(b for b in message.content if b.type == "tool_use")
                return self._to_response(tool_block)
            except APIStatusError as e:
                if e.status_code != 529:
                    raise
                last_error = e
                if attempt < max_attempts - 1:
                    delay = (2 ** attempt) + random.uniform(0, 1)
                    time.sleep(delay)
        raise last_error

    def _to_response(self, tool_block) -> LLMResponse:
        name = tool_block.name
        inp = tool_block.input

        if name == "ask_clarification":
            return LLMResponse(status="ambiguous", sql=None, clarifying_question=inp["question"],
                                target_db=None, mongo_query=None, cypher=None)
        if name == "query_postgres":
            return LLMResponse(status="clear", sql=inp["sql"], clarifying_question=None,
                                target_db="postgres", mongo_query=None, cypher=None)
        if name == "query_mongo":
            return LLMResponse(status="clear", sql=None, clarifying_question=None,
                                target_db="mongo", mongo_query=inp, cypher=None)
        if name == "query_neo4j":
            return LLMResponse(status="clear", sql=None, clarifying_question=None,
                                target_db="neo4j", mongo_query=None, cypher=inp["cypher"])
        raise ValueError(f"unexpected tool called: {name}")