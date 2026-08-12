"""
Plain-text description of MongoDB's collections, fed to the LLM so it
knows what fields exist when generating Mongo queries. Mirrors what
schema_context.py does for Postgres.
"""

MONGO_SCHEMA_CONTEXT = """
Database: multibase

Collection: editorials
  Editorial writeup + discussion thread for a problem. Not every problem
  has one (120 of 320 problems are represented).
  {
    problem_id: int          -> matches problems.id in Postgres
    problem_title: string
    editorial: {
      author: string
      approach: string       -> dp, greedy, binary search, two pointers, graph traversal, math
      content: string
    }
    comments: [
      { student_name: string, text: string, posted_at: datetime, upvotes: int }
    ]
  }

Collection: problem_statements
  Full problem text - description, constraints, sample input/output. One
  document per problem (320 total, 1:1 with Postgres problems).
  {
    problem_id: int          -> matches problems.id in Postgres
    problem_title: string
    statement: string
    constraints: [string]
    examples: [
      { input: string, output: string, explanation: string or null }
    ]
  }

Collection: submission_code
  The actual submitted code for a sample of submissions (Postgres only
  stores verdict/runtime metadata, not the code itself).
  {
    submission_id: int       -> matches submissions.id in Postgres
    language: string         -> cpp, python, java, javascript
    verdict: string          -> AC, WA, TLE, RE, MLE
    code: string
    line_count: int
  }
  Only a sample of ~500 submissions have code stored, not all ~12k.
"""