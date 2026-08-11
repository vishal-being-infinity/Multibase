"""
Plain-text description of the database schema, fed to the LLM so it knows
what tables/columns exist. Kept as a hand-written constant for now - could
be auto-generated from information_schema later if the schema grows.
"""

SCHEMA_CONTEXT = """
Tables:

platforms(id, name)
  - name: Codeforces, LeetCode, CodeChef

students(id, name, email, college, rating, joined_date)
  - rating: integer, roughly 800-2600

contests(id, platform_id -> platforms.id, name, contest_type, start_time, duration_minutes)
  - contest_type: weekly, rated, educational

problems(id, contest_id -> contests.id, title, difficulty, points, tags)
  - difficulty: easy, medium, hard
  - tags: text array, e.g. dp, graphs, greedy

submissions(id, student_id -> students.id, problem_id -> problems.id, contest_id -> contests.id,
            verdict, language, runtime_ms, submitted_at)
  - verdict: AC, WA, TLE, RE, MLE
  - language: cpp, python, java, javascript
"""