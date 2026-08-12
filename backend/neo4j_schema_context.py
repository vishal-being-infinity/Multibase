"""
Plain-text description of the Neo4j graph, fed to the LLM so it knows
what node labels, relationship types, and properties exist when
generating Cypher.
"""

NEO4J_SCHEMA_CONTEXT = """
Graph database - social and similarity relationships (not available in Postgres/Mongo).

Nodes:
  (:Student {id, name})   -> id matches students.id in Postgres
  (:Problem {id, title})  -> id matches problems.id in Postgres

Relationships:
  (:Student)-[:MENTORS]->(:Student)        - directed, mentor -> mentee
  (:Student)-[:FOLLOWS]->(:Student)        - directed, follower -> followed
  (:Student)-[:RIVAL_OF]-(:Student)        - undirected, similar rating
  (:Problem)-[:SIMILAR_TO {shared_tags}]-(:Problem) - undirected, overlapping tags

Use this graph for relationship/connection questions: mentorship chains,
who follows whom, rivalries, or which problems are similar to a given one.
Use Postgres instead for anything about ratings, contest results, or
submission counts - this graph only has id/name/title, not that data.
"""