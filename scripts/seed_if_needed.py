"""
Seeds Postgres and Mongo only if they're currently empty. Safe to run on
every `make up` - won't duplicate data on repeat runs, which is what
makes a single always-run command possible instead of a separate manual
seed step.
"""

import os
import subprocess
import sys
import time

import psycopg
from dotenv import load_dotenv
from pymongo import MongoClient

load_dotenv()


# retries the connection briefly - postgres may not be accepting connections
# in the first moment after the container starts, even though it's "up"
def wait_for_postgres(retries=10, delay=1.5):
    last_error = None
    for _ in range(retries):
        try:
            conn = psycopg.connect(os.getenv("DATABASE_URL"))
            conn.close()
            return
        except Exception as e:
            last_error = e
            time.sleep(delay)
    raise RuntimeError(f"postgres not reachable after {retries} retries: {last_error}")


def postgres_needs_seed():
    conn = psycopg.connect(os.getenv("DATABASE_URL"))
    with conn.cursor() as cur:
        cur.execute("SELECT COUNT(*) FROM students")
        count = cur.fetchone()[0]
    conn.close()
    return count == 0


def mongo_needs_seed():
    client = MongoClient(os.getenv("MONGO_URL"))
    db = client["multibase"]
    return db.editorials.count_documents({}) == 0


def main():
    wait_for_postgres()

    if postgres_needs_seed():
        print("postgres is empty - seeding...")
        subprocess.run([sys.executable, "/app/scripts/seed_postgres.py"], check=True)
    else:
        print("postgres already has data - skipping")

    if mongo_needs_seed():
        print("mongo is empty - seeding...")
        subprocess.run([sys.executable, "/app/scripts/seed_mongo.py"], check=True)
    else:
        print("mongo already has data - skipping")


if __name__ == "__main__":
    main()