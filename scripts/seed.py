"""
Seeds the database with fake but realistic competitive programming data.
Run after schema.sql is applied. Safe to re-run - just wipes and reseeds.
"""

import os
import random
from datetime import datetime, timedelta

import psycopg
from dotenv import load_dotenv
from faker import Faker

load_dotenv()
fake = Faker()

NUM_STUDENTS = 300
NUM_CONTESTS = 40
PROBLEMS_PER_CONTEST = 8

PLATFORMS = ["Codeforces", "LeetCode", "CodeChef"]
DIFFICULTIES = ["easy", "medium", "hard"]
TAGS_POOL = ["dp", "graphs", "greedy", "math", "strings", "trees", "binary-search", "two-pointers"]
LANGUAGES = ["cpp", "python", "java", "javascript"]
VERDICTS = ["AC", "WA", "TLE", "RE", "MLE"]
# most submissions succeed eventually, but not all - weighted to feel real
VERDICT_WEIGHTS = [55, 25, 10, 6, 4]


# opens a psycopg connection using DATABASE_URL from .env
def get_connection():
    return psycopg.connect(os.getenv("DATABASE_URL"))


# clears all tables so the script can be re-run without duplicate data
def wipe_tables(cur):
    cur.execute("TRUNCATE submissions, problems, contests, students, platforms RESTART IDENTITY CASCADE")


# inserts the 3 platforms, returns a name -> id lookup
def seed_platforms(cur):
    for name in PLATFORMS:
        cur.execute("INSERT INTO platforms (name) VALUES (%s) RETURNING id", (name,))
    cur.execute("SELECT id, name FROM platforms")
    return {name: pid for pid, name in cur.fetchall()}


# inserts n fake students with random ratings and join dates, returns their ids
def seed_students(cur, n):
    rows = []
    for _ in range(n):
        joined = fake.date_between(start_date="-2y", end_date="-1M")
        rows.append((
            fake.name(),
            fake.unique.email(),
            fake.company() + " University",
            random.randint(800, 2600),  # rating spread
            joined,
        ))
    cur.executemany(
        "INSERT INTO students (name, email, college, rating, joined_date) VALUES (%s, %s, %s, %s, %s)",
        rows,
    )
    cur.execute("SELECT id FROM students")
    return [r[0] for r in cur.fetchall()]


# inserts n contests spread across platforms and the last year, returns their ids
def seed_contests(cur, platform_ids, n):
    contest_types = ["weekly", "rated", "educational"]
    rows = []
    for i in range(n):
        platform = random.choice(list(platform_ids.values()))
        start = datetime.now() - timedelta(weeks=random.randint(1, 52))
        rows.append((
            platform,
            f"{random.choice(contest_types).capitalize()} Contest {i+1}",
            random.choice(contest_types),
            start,
            random.choice([90, 120, 150, 180]),
        ))
    cur.executemany(
        "INSERT INTO contests (platform_id, name, contest_type, start_time, duration_minutes) VALUES (%s, %s, %s, %s, %s)",
        rows,
    )
    cur.execute("SELECT id FROM contests")
    return [r[0] for r in cur.fetchall()]


# inserts a fixed number of problems per contest, returns {contest_id: [problem_ids]}
def seed_problems(cur, contest_ids):
    rows = []
    problem_ids_by_contest = {}
    for contest_id in contest_ids:
        for _ in range(PROBLEMS_PER_CONTEST):
            difficulty = random.choice(DIFFICULTIES)
            points = {"easy": 100, "medium": 300, "hard": 600}[difficulty]
            tags = random.sample(TAGS_POOL, k=random.randint(1, 3))
            rows.append((contest_id, fake.sentence(nb_words=3).rstrip("."), difficulty, points, tags))
    cur.executemany(
        "INSERT INTO problems (contest_id, title, difficulty, points, tags) VALUES (%s, %s, %s, %s, %s)",
        rows,
    )
    cur.execute("SELECT id, contest_id FROM problems")
    for pid, cid in cur.fetchall():
        problem_ids_by_contest.setdefault(cid, []).append(pid)
    return problem_ids_by_contest


# for each student, attempts a handful of contests/problems and inserts a submission with a weighted-random verdict
def seed_submissions(cur, student_ids, problem_ids_by_contest):
    rows = []
    for student_id in student_ids:
        attempted_contests = random.sample(
            list(problem_ids_by_contest.keys()),
            k=random.randint(3, 15),
        )
        for contest_id in attempted_contests:
            problems = problem_ids_by_contest[contest_id]
            attempted_problems = random.sample(problems, k=random.randint(1, len(problems)))
            for problem_id in attempted_problems:
                submitted_at = fake.date_time_between(start_date="-1y", end_date="now")
                rows.append((
                    student_id,
                    problem_id,
                    contest_id,
                    random.choices(VERDICTS, weights=VERDICT_WEIGHTS)[0],
                    random.choice(LANGUAGES),
                    random.randint(20, 4000),
                    submitted_at,
                ))
    cur.executemany(
        """INSERT INTO submissions (student_id, problem_id, contest_id, verdict, language, runtime_ms, submitted_at)
           VALUES (%s, %s, %s, %s, %s, %s, %s)""",
        rows,
    )
    return len(rows)


# wipes the db and reseeds all tables in dependency order, then prints a summary
def main():
    with get_connection() as conn:
        with conn.cursor() as cur:
            wipe_tables(cur)
            platform_ids = seed_platforms(cur)
            student_ids = seed_students(cur, NUM_STUDENTS)
            contest_ids = seed_contests(cur, platform_ids, NUM_CONTESTS)
            problem_ids_by_contest = seed_problems(cur, contest_ids)
            submission_count = seed_submissions(cur, student_ids, problem_ids_by_contest)
        conn.commit()

    print(f"seeded {len(student_ids)} students, {len(contest_ids)} contests, "
          f"{sum(len(v) for v in problem_ids_by_contest.values())} problems, "
          f"{submission_count} submissions")


if __name__ == "__main__":
    main()