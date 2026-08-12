"""
Gemini implementation of LLMProvider. Uses response_schema (Gemini's
structured-output mode) so the response shape is guaranteed, same
guarantee Claude gets from forced tool use. Mirrors ClaudeProvider's
three-database routing (Postgres/Mongo/Neo4j) via a discriminated
response schema instead of tool selection, since Gemini's structured
output is schema-based rather than multi-tool-based.
"""

import os
import json

from google import genai
from google.genai import types

from .base import LLMProvider, LLMResponse

RESPONSE_SCHEMA = {
    "type": "OBJECT",
    "properties": {
        "status": {"type": "STRING", "enum": ["clear", "ambiguous"]},
        "target_db": {"type": "STRING", "enum": ["postgres", "mongo", "neo4j"]},
        "sql": {"type": "STRING"},
        "mongo_collection": {"type": "STRING", "enum": ["editorials", "problem_statements", "submission_code"]},
        "mongo_operation": {"type": "STRING", "enum": ["find", "aggregate"]},
        "mongo_filter": {"type": "OBJECT"},
        "mongo_pipeline": {"type": "ARRAY", "items": {"type": "OBJECT"}},
        "mongo_limit": {"type": "INTEGER"},
        "cypher": {"type": "STRING"},
        "clarifying_question": {"type": "STRING"},
    },
    "required": ["status"],
}

SYSTEM_PROMPT = """You answer questions about a competitive programming platform by
routing to the correct database and generating the right query, in one step.

Three databases are available:
- Postgres (target_db="postgres"): structured data - students, contests, problems
  (metadata only), submissions (metadata only). Write the query in "sql".
- MongoDB (target_db="mongo"): flexible content - editorial writeups + comments, full
  problem statements (constraints, examples), and submitted code text. Set
  mongo_collection, mongo_operation ("find" or "aggregate"), and mongo_filter or
  mongo_pipeline accordingly.
- Neo4j (target_db="neo4j"): relationships - mentorship, follows, rivalries between
  students, and problem similarity. Write the query in "cypher".

Rules:
- Pick exactly ONE database per question.
- Only generate read-only operations. Never write/modify data.
- If the question is genuinely ambiguous, set status to "ambiguous" and fill in
  clarifying_question with ONE short, specific question.
- If answerable, set status to "clear" and fill in target_db plus the matching
  query fields for that database.
- Always use the exact table/column names, collection/field names, or
  node/relationship names given in the schemas."""


class GeminiProvider(LLMProvider):
    def __init__(self):
        self.client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))
        self.model = "gemini-2.5-flash"

    # sends conversation history + all three schema contexts to Gemini, forces schema-conformant JSON output
    def process_question(self, history: list, schema_context: str, mongo_schema_context: str = "", neo4j_schema_context: str = "") -> LLMResponse:
        conversation = "\n".join(f"{turn['role']}: {turn['content']}" for turn in history)
        combined_schema = (
            f"Postgres schema:\n{schema_context}\n\n"
            f"MongoDB schema:\n{mongo_schema_context}\n\n"
            f"Neo4j schema:\n{neo4j_schema_context}"
        )
        prompt = f"{combined_schema}\n\nConversation:\n{conversation}"

        response = self.client.models.generate_content(
            model=self.model,
            contents=prompt,
            config=types.GenerateContentConfig(
                system_instruction=SYSTEM_PROMPT,
                response_mime_type="application/json",
                response_schema=RESPONSE_SCHEMA,
            ),
        )

        result = json.loads(response.text)
        return self._to_response(result)

    # normalizes Gemini's flat schema into the same LLMResponse shape ClaudeProvider produces
    def _to_response(self, result: dict) -> LLMResponse:
        if result.get("status") == "ambiguous":
            return LLMResponse(status="ambiguous", sql=None, clarifying_question=result.get("clarifying_question"),
                                target_db=None, mongo_query=None, cypher=None)

        target_db = result.get("target_db")
        if target_db == "postgres":
            return LLMResponse(status="clear", sql=result.get("sql"), clarifying_question=None,
                                target_db="postgres", mongo_query=None, cypher=None)
        if target_db == "mongo":
            mongo_query = {
                "collection": result.get("mongo_collection"),
                "operation": result.get("mongo_operation"),
                "filter": result.get("mongo_filter"),
                "pipeline": result.get("mongo_pipeline"),
                "limit": result.get("mongo_limit"),
            }
            return LLMResponse(status="clear", sql=None, clarifying_question=None,
                                target_db="mongo", mongo_query=mongo_query, cypher=None)
        if target_db == "neo4j":
            return LLMResponse(status="clear", sql=None, clarifying_question=None,
                                target_db="neo4j", mongo_query=None, cypher=result.get("cypher"))

        raise ValueError(f"unexpected or missing target_db: {target_db}")