"""
FastAPI app entrypoint.
/health - confirms the API and DB are reachable
/query  - runs raw SQL against Postgres (temporary, no LLM yet, no safety checks yet)
"""

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from llm.factory import get_llm_provider
from schema_context import SCHEMA_CONTEXT
from llm.base import Turn

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
    llm = get_llm_provider()

    # build the full turn list: prior history + this new question
    turns = req.history + [{"role": "user", "content": req.question}]

    result = llm.process_question(turns, SCHEMA_CONTEXT)

    if result["status"] == "ambiguous":
        return {"status": "ambiguous", "clarifying_question": result["clarifying_question"]}

    try:
        rows = run_query(result["sql"])
        return {"status": "ok", "sql": result["sql"], "row_count": len(rows), "rows": rows}
    except UnsafeQueryError as e:
        raise HTTPException(status_code=403, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"generated SQL failed: {e}")