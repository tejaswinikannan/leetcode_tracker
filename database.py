import sqlite3
from datetime import date
from typing import Optional
import os

DB_PATH = os.path.join(os.path.dirname(__file__), "leetcode_tracker.db")


def get_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = get_connection()
    c = conn.cursor()
    c.executescript("""
        CREATE TABLE IF NOT EXISTS problems (
            problem_id      INTEGER PRIMARY KEY AUTOINCREMENT,
            leetcode_number INTEGER NOT NULL,
            title           TEXT NOT NULL,
            link            TEXT NOT NULL,
            created_date    TEXT NOT NULL,
            difficulty      TEXT DEFAULT 'Medium'
        );

        CREATE TABLE IF NOT EXISTS problem_attempts (
            attempt_id   INTEGER PRIMARY KEY AUTOINCREMENT,
            problem_id   INTEGER NOT NULL REFERENCES problems(problem_id),
            attempt_date TEXT NOT NULL,
            bucket       TEXT NOT NULL CHECK(bucket IN ('Learning','Practicing','Mastered')),
            result       TEXT NOT NULL CHECK(result IN ('solved','failed','partial')),
            solve_time   INTEGER,
            notes        TEXT
        );
    """)

    # Migration: add difficulty to existing DBs that don't have it yet
    cols = [row[1] for row in c.execute("PRAGMA table_info(problems)").fetchall()]
    if "difficulty" not in cols:
        c.execute("ALTER TABLE problems ADD COLUMN difficulty TEXT DEFAULT 'Medium'")

    conn.commit()
    conn.close()


def add_problem(leetcode_number: int, title: str, link: str, difficulty: str = "Medium") -> int:
    conn = get_connection()
    c = conn.cursor()
    c.execute(
        "INSERT INTO problems (leetcode_number, title, link, created_date, difficulty) VALUES (?,?,?,?,?)",
        (leetcode_number, title, link, date.today().isoformat(), difficulty),
    )
    problem_id = c.lastrowid
    conn.commit()
    conn.close()
    return problem_id


def log_attempt(
    problem_id: int,
    bucket: str,
    result: str,
    attempt_date: Optional[str] = None,
    solve_time: Optional[int] = None,
    notes: Optional[str] = None,
):
    conn = get_connection()
    c = conn.cursor()
    c.execute(
        """INSERT INTO problem_attempts
           (problem_id, attempt_date, bucket, result, solve_time, notes)
           VALUES (?,?,?,?,?,?)""",
        (
            problem_id,
            attempt_date or date.today().isoformat(),
            bucket,
            result,
            solve_time,
            notes,
        ),
    )
    conn.commit()
    conn.close()


def get_all_problems():
    conn = get_connection()
    rows = conn.execute("SELECT * FROM problems ORDER BY leetcode_number").fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_problem_by_id(problem_id: int):
    conn = get_connection()
    row = conn.execute("SELECT * FROM problems WHERE problem_id=?", (problem_id,)).fetchone()
    conn.close()
    return dict(row) if row else None


def get_attempts_for_problem(problem_id: int):
    conn = get_connection()
    rows = conn.execute(
        "SELECT * FROM problem_attempts WHERE problem_id=? ORDER BY attempt_date DESC",
        (problem_id,),
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_all_attempts():
    conn = get_connection()
    rows = conn.execute("""
        SELECT pa.*, p.leetcode_number, p.title, p.link
        FROM problem_attempts pa
        JOIN problems p ON pa.problem_id = p.problem_id
        ORDER BY pa.attempt_date DESC
    """).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def problem_number_exists(leetcode_number: int) -> bool:
    conn = get_connection()
    row = conn.execute(
        "SELECT 1 FROM problems WHERE leetcode_number=?", (leetcode_number,)
    ).fetchone()
    conn.close()
    return row is not None


def get_problem_by_number(leetcode_number: int):
    conn = get_connection()
    row = conn.execute(
        "SELECT * FROM problems WHERE leetcode_number=?", (leetcode_number,)
    ).fetchone()
    conn.close()
    return dict(row) if row else None