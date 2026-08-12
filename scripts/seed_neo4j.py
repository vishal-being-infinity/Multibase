"""
Seeds Neo4j (AuraDB) with a social graph over students (mentorship,
follows, rivalries) and a similarity graph over problems (shared tags).
Node ids match Postgres's students.id / problems.id - same loose-linking
convention used for Mongo, no foreign key, just a shared id.
"""

import os
import random

import psycopg
from dotenv import load_dotenv
from neo4j import GraphDatabase

load_dotenv()

NUM_MENTORSHIPS = 60
NUM_FOLLOWS = 400
NUM_RIVALRIES = 150
SIMILARITY_SAMPLE_RATE = 0.05  # fraction of tag-overlapping problem pairs to link - avoids O(n^2) blowup


def get_driver():
    return GraphDatabase.driver(
        os.getenv("NEO4J_URI"),
        auth=(os.getenv("NEO4J_USER"), os.getenv("NEO4J_PASSWORD")),
    )


def fetch_students(pg_conn):
    with pg_conn.cursor() as cur:
        cur.execute("SELECT id, name, rating, college FROM students")
        return cur.fetchall()


def fetch_problems(pg_conn):
    with pg_conn.cursor() as cur:
        cur.execute("SELECT id, title, tags FROM problems")
        return cur.fetchall()


# wipes the whole graph so this script is safely re-runnable, same pattern as the other seed scripts
def wipe_graph(session):
    session.run("MATCH (n) DETACH DELETE n")


def create_student_nodes(session, students):
    session.run(
        "UNWIND $rows AS row MERGE (s:Student {id: row.id}) SET s.name = row.name",
        rows=[{"id": sid, "name": name} for sid, name, _, _ in students],
    )


def create_problem_nodes(session, problems):
    session.run(
        "UNWIND $rows AS row MERGE (p:Problem {id: row.id}) SET p.title = row.title",
        rows=[{"id": pid, "title": title} for pid, title, _ in problems],
    )


# higher-rated students mentor lower-rated ones, picked from random pairs
def create_mentorships(session, students):
    pairs = []
    for _ in range(NUM_MENTORSHIPS):
        mentor, mentee = random.sample(students, 2)
        if mentor[2] > mentee[2]:
            pairs.append((mentor[0], mentee[0]))
    session.run(
        "UNWIND $rows AS row MATCH (a:Student {id: row.a}), (b:Student {id: row.b}) MERGE (a)-[:MENTORS]->(b)",
        rows=[{"a": a, "b": b} for a, b in pairs],
    )
    return len(pairs)


def create_follows(session, students):
    ids = [s[0] for s in students]
    pairs = set()
    while len(pairs) < NUM_FOLLOWS:
        a, b = random.sample(ids, 2)
        pairs.add((a, b))
    session.run(
        "UNWIND $rows AS row MATCH (a:Student {id: row.a}), (b:Student {id: row.b}) MERGE (a)-[:FOLLOWS]->(b)",
        rows=[{"a": a, "b": b} for a, b in pairs],
    )
    return len(pairs)


# rivals = students within 100 rating points of each other
def create_rivalries(session, students):
    pairs = set()
    attempts = 0
    while len(pairs) < NUM_RIVALRIES and attempts < NUM_RIVALRIES * 20:
        a, b = random.sample(students, 2)
        attempts += 1
        if abs(a[2] - b[2]) <= 100:
            pairs.add(tuple(sorted([a[0], b[0]])))
    session.run(
        "UNWIND $rows AS row MATCH (a:Student {id: row.a}), (b:Student {id: row.b}) MERGE (a)-[:RIVAL_OF]-(b)",
        rows=[{"a": a, "b": b} for a, b in pairs],
    )
    return len(pairs)


# links problems that share at least one tag, sampled rather than exhaustive
def create_similarities(session, problems):
    pairs = []
    for i, (pid1, _, tags1) in enumerate(problems):
        if not tags1:
            continue
        for pid2, _, tags2 in problems[i + 1:]:
            if not tags2:
                continue
            shared = set(tags1) & set(tags2)
            if shared and random.random() < SIMILARITY_SAMPLE_RATE:
                pairs.append((pid1, pid2, list(shared)))
    session.run(
        """UNWIND $rows AS row
           MATCH (a:Problem {id: row.a}), (b:Problem {id: row.b})
           MERGE (a)-[r:SIMILAR_TO]-(b)
           SET r.shared_tags = row.tags""",
        rows=[{"a": a, "b": b, "tags": tags} for a, b, tags in pairs],
    )
    return len(pairs)


def main():
    pg_conn = psycopg.connect(os.getenv("DATABASE_URL"))
    students = fetch_students(pg_conn)
    problems = fetch_problems(pg_conn)
    pg_conn.close()

    driver = get_driver()
    with driver.session() as session:
        wipe_graph(session)
        create_student_nodes(session, students)
        create_problem_nodes(session, problems)
        n_mentor = create_mentorships(session, students)
        n_follow = create_follows(session, students)
        n_rival = create_rivalries(session, students)
        n_similar = create_similarities(session, problems)
    driver.close()

    print(f"seeded {len(students)} students, {len(problems)} problems, "
          f"{n_mentor} mentorships, {n_follow} follows, "
          f"{n_rival} rivalries, {n_similar} similarities")


if __name__ == "__main__":
    main()