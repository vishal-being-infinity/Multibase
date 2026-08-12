"""
Seeds MongoDB (Atlas) with three collections that hold content Postgres
doesn't - editorials/discussions, full problem statements, and submitted
code. Each links back to a Postgres id (problem_id or submission_id) but
there's no foreign key - just a shared id convention, checked at query
time by the application, not enforced by either database.
"""

import os
import random

import psycopg
from dotenv import load_dotenv
from faker import Faker
from pymongo import MongoClient

load_dotenv()
fake = Faker()

APPROACHES = ["dp", "greedy", "binary search", "two pointers", "graph traversal", "math"]
LANGUAGES = ["cpp", "python", "java", "javascript"]

NUM_EDITORIALS = 120       # not every problem has one - mirrors real judges
NUM_CODE_SAMPLES = 500     # sample of submissions, not all ~12k


def get_client():
    return MongoClient(os.getenv("MONGO_URL"))


# --- editorials ---

def build_editorial_doc(problem_id, problem_title):
    return {
        "problem_id": problem_id,
        "problem_title": problem_title,
        "editorial": {
            "author": fake.name(),
            "approach": random.choice(APPROACHES),
            "content": fake.paragraph(nb_sentences=6),
        },
        "comments": [
            {
                "student_name": fake.name(),
                "text": fake.sentence(nb_words=12),
                "posted_at": fake.date_time_between(start_date="-1y", end_date="now"),
                "upvotes": random.randint(0, 40),
            }
            for _ in range(random.randint(0, 8))
        ],
    }


# --- problem statements ---

def build_statement_doc(problem_id, problem_title, difficulty):
    num_examples = random.randint(1, 3)
    return {
        "problem_id": problem_id,
        "problem_title": problem_title,
        "statement": fake.paragraph(nb_sentences=4),
        "constraints": [
            f"1 <= n <= {random.choice([1000, 10000, 100000, 1000000])}",
            f"time limit: {random.choice([1, 2, 3])} seconds",
        ],
        "examples": [
            {
                "input": " ".join(str(random.randint(1, 100)) for _ in range(random.randint(2, 5))),
                "output": str(random.randint(1, 1000)),
                "explanation": fake.sentence(nb_words=8) if random.random() > 0.5 else None,
            }
            for _ in range(num_examples)
        ],
    }


# --- submission code ---

def build_code_doc(submission_id, language, verdict):
    # not real code - a placeholder block, since realism here doesn't matter for query-routing purposes
    return {
        "submission_id": submission_id,
        "language": language,
        "verdict": verdict,
        "code": f"// {language} submission\n" + "\n".join(fake.sentence() for _ in range(random.randint(5, 20))),
        "line_count": random.randint(15, 120),
    }


def fetch_all_problems(pg_conn):
    with pg_conn.cursor() as cur:
        cur.execute("SELECT id, title, difficulty FROM problems")
        return cur.fetchall()


def fetch_submission_sample(pg_conn, n):
    with pg_conn.cursor() as cur:
        cur.execute("SELECT id, language, verdict FROM submissions ORDER BY random() LIMIT %s", (n,))
        return cur.fetchall()


def main():
    pg_conn = psycopg.connect(os.getenv("DATABASE_URL"))
    all_problems = fetch_all_problems(pg_conn)
    submission_sample = fetch_submission_sample(pg_conn, NUM_CODE_SAMPLES)
    pg_conn.close()

    client = get_client()
    db = client["multibase"]

    # editorials - subset of problems
    db.editorials.drop()
    editorial_problems = random.sample(all_problems, NUM_EDITORIALS)
    editorial_docs = [build_editorial_doc(pid, title) for pid, title, _ in editorial_problems]
    db.editorials.insert_many(editorial_docs)

    # problem_statements - all problems, 1:1
    db.problem_statements.drop()
    statement_docs = [build_statement_doc(pid, title, diff) for pid, title, diff in all_problems]
    db.problem_statements.insert_many(statement_docs)

    # submission_code - sample of submissions
    db.submission_code.drop()
    code_docs = [build_code_doc(sid, lang, verdict) for sid, lang, verdict in submission_sample]
    db.submission_code.insert_many(code_docs)

    print(f"seeded {len(editorial_docs)} editorials, "
          f"{len(statement_docs)} problem statements, "
          f"{len(code_docs)} code samples")


if __name__ == "__main__":
    main()