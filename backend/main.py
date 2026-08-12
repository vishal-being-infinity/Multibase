"""
FastAPI app entrypoint.
/health - confirms the API and DB are reachable
/query  - runs raw SQL against Postgres (temporary, no LLM yet, no safety checks yet)
"""

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from schema_context import SCHEMA_CONTEXT
from llm.base import Turn
from anthropic import APIStatusError
from llm.factory import get_llm_providers
from mongo_db import run_find, run_aggregate, UnsafeMongoQueryError
from mongo_schema_context import MONGO_SCHEMA_CONTEXT
from neo4j_db import run_cypher, UnsafeCypherError
from neo4j_schema_context import NEO4J_SCHEMA_CONTEXT

from fastapi.middleware.cors import CORSMiddleware
from db import run_query, UnsafeQueryError

app = FastAPI(title="NL2SQL API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# request body shape for the /query endpoint
class QueryRequest(BaseModel):
    sql: str


# confirms the API is up and can reach the database
@app.get("/health")
def health():
    try:
        run_query("SELECT 1")
        return {"status": "ok", "db": "connected"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"db connection failed: {e}")


# runs raw SQL and returns the rows - placeholder until the LLM layer replaces manual SQL input
@app.post("/query")
def query(req: QueryRequest):
    try:
        rows = run_query(req.sql)
        return {"row_count": len(rows), "rows": rows}
    except UnsafeQueryError as e:
        raise HTTPException(status_code=403, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


# request body shape for /ask - history lets the client resend the conversation so far
class AskRequest(BaseModel):
    question: str
    history: list[Turn] = []


# takes a plain-english question (+ prior conversation), asks the LLM to clarify or generate SQL, runs it if clear
@app.post("/ask")
def ask(req: AskRequest):
    turns = req.history + [{"role": "user", "content": req.question}]
    providers = get_llm_providers()

    result = None
    last_error = None
    for provider in providers:
        try:
            result = provider.process_question(turns, SCHEMA_CONTEXT, MONGO_SCHEMA_CONTEXT, NEO4J_SCHEMA_CONTEXT)
            break
        except Exception as e:
            last_error = e
            continue

    if result is None:
        raise HTTPException(status_code=503, detail=f"all LLM providers failed: {last_error}")

    if result["status"] == "ambiguous":
        return {"status": "ambiguous", "clarifying_question": result["clarifying_question"]}

    try:
        if result["target_db"] == "postgres":
            rows = run_query(result["sql"])
            return {"status": "ok", "source": "postgres", "sql": result["sql"], "row_count": len(rows), "rows": rows}

        elif result["target_db"] == "mongo":
            mq = result["mongo_query"]
            operation = mq.get("operation") or ("aggregate" if mq.get("pipeline") else "find")
            if operation == "find":
                rows = run_find(mq["collection"], mq.get("filter", {}), mq.get("limit", 20))
            else:
                rows = run_aggregate(mq["collection"], mq.get("pipeline", []))
            return {"status": "ok", "source": "mongo", "sql": f"db.{mq['collection']}.{operation}(...)",
                    "row_count": len(rows), "rows": rows}
        elif result["target_db"] == "neo4j":
            rows = run_cypher(result["cypher"])
            return {"status": "ok", "source": "neo4j", "sql": result["cypher"], "row_count": len(rows), "rows": rows}

        raise HTTPException(status_code=500, detail=f"unknown target_db: {result['target_db']}")

    except (UnsafeQueryError, UnsafeMongoQueryError, UnsafeCypherError) as e:
        raise HTTPException(status_code=403, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"query failed: {e}")