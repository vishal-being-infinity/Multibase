"""
MongoDB connection handling for the backend. Uses a read-only Atlas user
for serving queries - seeding always goes through MONGO_URL (full access)
via scripts/seed_mongo.py directly, never through this module.
"""

import os

from dotenv import load_dotenv
from pymongo import MongoClient

load_dotenv()

# read-only role - this client can never write, even if app-level logic below has a bug
_client = MongoClient(os.getenv("MONGO_READONLY_URL"))
_db = _client["multibase"]

# the only two operations ever exposed - insert/update/delete/drop simply
# aren't reachable through this module, regardless of what a query "says"
ALLOWED_COLLECTIONS = {"editorials", "problem_statements", "submission_code"}


class UnsafeMongoQueryError(Exception):
    pass


# runs a find query against an allowed collection, returns a list of plain dicts
def run_find(collection: str, filter: dict, limit: int = 20) -> list[dict]:
    if collection not in ALLOWED_COLLECTIONS:
        raise UnsafeMongoQueryError(f"unknown or disallowed collection: {collection}")
    cursor = _db[collection].find(filter).limit(limit)
    return [_stringify_id(doc) for doc in cursor]


# runs an aggregation pipeline against an allowed collection, returns a list of plain dicts
def run_aggregate(collection: str, pipeline: list) -> list[dict]:
    if collection not in ALLOWED_COLLECTIONS:
        raise UnsafeMongoQueryError(f"unknown or disallowed collection: {collection}")
    # belt-and-suspenders: reject any stage that could write, even though
    # aggregate() itself can't run insert/update - $merge and $out can write
    # results back to a collection, so we block them explicitly
    for stage in pipeline:
        if "$merge" in stage or "$out" in stage:
            raise UnsafeMongoQueryError("aggregation stages that write ($merge, $out) are not allowed")
    cursor = _db[collection].aggregate(pipeline)
    return [_stringify_id(doc) for doc in cursor]


# mongo's ObjectId isn't JSON-serializable - convert ids to plain strings before returning
def _stringify_id(doc: dict) -> dict:
    doc = dict(doc)
    if "_id" in doc:
        doc["_id"] = str(doc["_id"])
    return doc