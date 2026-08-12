-- platforms table: codeforces, leetcode, codechef etc.
CREATE TABLE platforms (
    id SERIAL PRIMARY KEY,
    name VARCHAR(50) UNIQUE NOT NULL
);

CREATE TABLE students (
    id SERIAL PRIMARY KEY,
    name VARCHAR(100) NOT NULL,
    email VARCHAR(150) UNIQUE NOT NULL,
    college VARCHAR(150),
    rating INTEGER DEFAULT 1200,
    joined_date DATE NOT NULL
);

CREATE TABLE contests (
    id SERIAL PRIMARY KEY,
    platform_id INTEGER NOT NULL REFERENCES platforms(id),
    name VARCHAR(200) NOT NULL,
    contest_type VARCHAR(50) NOT NULL,   -- weekly / rated / educational
    start_time TIMESTAMP NOT NULL,
    duration_minutes INTEGER NOT NULL
);

CREATE TABLE problems (
    id SERIAL PRIMARY KEY,
    contest_id INTEGER NOT NULL REFERENCES contests(id),
    title VARCHAR(200) NOT NULL,
    difficulty VARCHAR(20) NOT NULL,     -- easy / medium / hard
    points INTEGER NOT NULL,
    tags TEXT[]                          -- e.g. {dp, graphs}
);

CREATE TABLE submissions (
    id SERIAL PRIMARY KEY,
    student_id INTEGER NOT NULL REFERENCES students(id),
    problem_id INTEGER NOT NULL REFERENCES problems(id),
    contest_id INTEGER NOT NULL REFERENCES contests(id),
    verdict VARCHAR(30) NOT NULL,        -- AC / WA / TLE / RE
    language VARCHAR(30) NOT NULL,
    runtime_ms INTEGER,
    submitted_at TIMESTAMP NOT NULL
);

-- indexes for the joins/filters we'll be querying a lot
CREATE INDEX idx_submissions_student ON submissions(student_id);
CREATE INDEX idx_submissions_problem ON submissions(problem_id);
CREATE INDEX idx_submissions_contest ON submissions(contest_id);
CREATE INDEX idx_problems_contest ON problems(contest_id);
CREATE INDEX idx_contests_platform ON contests(platform_id);