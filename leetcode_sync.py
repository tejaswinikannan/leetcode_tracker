"""
leetcode_sync.py
Polls LeetCode's GraphQL API for recent accepted submissions using session cookies.
Stores them in a `sync_queue` table as pending items to be reviewed and imported.
"""

import sqlite3
import requests
import json
from datetime import datetime, date
from database import get_connection, DB_PATH


# ── Ensure sync_queue table exists ──────────────────────────────────────────
def init_sync_table():
    conn = get_connection()
    conn.execute("""
        CREATE TABLE IF NOT EXISTS sync_queue (
            queue_id        INTEGER PRIMARY KEY AUTOINCREMENT,
            leetcode_number INTEGER NOT NULL,
            title           TEXT NOT NULL,
            title_slug      TEXT NOT NULL,
            link            TEXT NOT NULL,
            submission_date TEXT NOT NULL,
            lc_status       TEXT NOT NULL,
            runtime         TEXT,
            language        TEXT,
            difficulty      TEXT DEFAULT 'Medium',
            fetched_at      TEXT NOT NULL,
            status          TEXT NOT NULL DEFAULT 'pending'
                            CHECK(status IN ('pending','imported','skipped'))
        )
    """)
    # Migration for existing sync_queue tables
    cols = [row[1] for row in conn.execute("PRAGMA table_info(sync_queue)").fetchall()]
    if "difficulty" not in cols:
        conn.execute("ALTER TABLE sync_queue ADD COLUMN difficulty TEXT DEFAULT 'Medium'")
    conn.commit()
    conn.close()


# ── GraphQL query ────────────────────────────────────────────────────────────
SUBMISSION_QUERY = """
query recentAcSubmissions($username: String!, $limit: Int!) {
  recentAcSubmissionList(username: $username, limit: $limit) {
    id
    title
    titleSlug
    timestamp
    lang
    runtime
  }
}
"""

PROBLEM_QUERY = """
query problemInfo($titleSlug: String!) {
  question(titleSlug: $titleSlug) {
    questionFrontendId
    title
    titleSlug
    difficulty
  }
}
"""


def _graphql(query: str, variables: dict, session_cookie: str, csrf_token: str) -> dict:
    resp = requests.post(
        "https://leetcode.com/graphql/",
        json={"query": query, "variables": variables},
        headers={
            "Content-Type": "application/json",
            "Referer": "https://leetcode.com",
            "x-csrftoken": csrf_token,
        },
        cookies={
            "LEETCODE_SESSION": session_cookie,
            "csrftoken": csrf_token,
        },
        timeout=15,
    )
    resp.raise_for_status()
    return resp.json()


def fetch_recent_accepted(username: str, session_cookie: str, csrf_token: str, limit: int = 20) -> list[dict]:
    """Fetch last `limit` accepted submissions from LeetCode GraphQL."""
    data = _graphql(SUBMISSION_QUERY, {"username": username, "limit": limit}, session_cookie, csrf_token)
    submissions = data.get("data", {}).get("recentAcSubmissionList") or []
    return submissions


def fetch_problem_number(title_slug: str, session_cookie: str, csrf_token: str) -> int | None:
    """Look up a problem's frontend number and difficulty by its title slug.
    Returns (lc_number, difficulty) or (None, 'Medium') on failure.
    """
    try:
        data = _graphql(PROBLEM_QUERY, {"titleSlug": title_slug}, session_cookie, csrf_token)
        q = data.get("data", {}).get("question")
        if q:
            return int(q["questionFrontendId"]), q.get("difficulty", "Medium")
    except Exception:
        pass
    return None, "Medium"


def queue_new_submissions(username: str, session_cookie: str, csrf_token: str, limit: int = 20) -> int:
    """
    Pull recent accepted submissions, skip ones already queued or already
    tracked as problems, and insert new ones as 'pending'.
    Returns the count of newly queued items.
    """
    init_sync_table()
    submissions = fetch_recent_accepted(username, session_cookie, csrf_token, limit)

    conn = get_connection()
    added = 0

    for sub in submissions:
        title_slug = sub["titleSlug"]
        title      = sub["title"]
        timestamp  = int(sub["timestamp"])
        lang       = sub.get("lang", "")
        runtime    = sub.get("runtime", "")
        sub_date   = datetime.utcfromtimestamp(timestamp).date().isoformat()

        # Already queued?
        exists = conn.execute(
            "SELECT 1 FROM sync_queue WHERE title_slug=? AND submission_date=?",
            (title_slug, sub_date)
        ).fetchone()
        if exists:
            continue

        # Get problem number + difficulty (extra API call per new problem)
        lc_num, difficulty = fetch_problem_number(title_slug, session_cookie, csrf_token)
        if lc_num is None:
            continue

        # Already fully tracked (problem exists + has an attempt on same date)?
        prob = conn.execute(
            "SELECT problem_id FROM problems WHERE leetcode_number=?", (lc_num,)
        ).fetchone()
        if prob:
            attempt_exists = conn.execute(
                "SELECT 1 FROM problem_attempts WHERE problem_id=? AND attempt_date=?",
                (prob["problem_id"], sub_date)
            ).fetchone()
            if attempt_exists:
                continue

        link = f"https://leetcode.com/problems/{title_slug}/"
        conn.execute(
            """INSERT INTO sync_queue
               (leetcode_number, title, title_slug, link, submission_date,
                lc_status, runtime, language, difficulty, fetched_at)
               VALUES (?,?,?,?,?,?,?,?,?,?)""",
            (lc_num, title, title_slug, link, sub_date,
             "Accepted", runtime, lang, difficulty, date.today().isoformat())
        )
        added += 1

    conn.commit()
    conn.close()
    return added


def get_pending_queue() -> list[dict]:
    init_sync_table()
    conn = get_connection()
    rows = conn.execute(
        "SELECT * FROM sync_queue WHERE status='pending' ORDER BY submission_date DESC"
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def mark_queue_item(queue_id: int, status: str):
    conn = get_connection()
    conn.execute("UPDATE sync_queue SET status=? WHERE queue_id=?", (status, queue_id))
    conn.commit()
    conn.close()


def get_queue_counts() -> dict:
    init_sync_table()
    conn = get_connection()
    row = conn.execute("""
        SELECT
            SUM(CASE WHEN status='pending'  THEN 1 ELSE 0 END) as pending,
            SUM(CASE WHEN status='imported' THEN 1 ELSE 0 END) as imported,
            SUM(CASE WHEN status='skipped'  THEN 1 ELSE 0 END) as skipped
        FROM sync_queue
    """).fetchone()
    conn.close()
    return dict(row) if row else {"pending": 0, "imported": 0, "skipped": 0}