import random
from datetime import date
import pandas as pd
from database import get_connection


def get_problems_with_current_bucket() -> pd.DataFrame:
    """
    Returns a DataFrame with one row per problem showing its latest bucket
    and days since last attempt.
    """
    conn = get_connection()
    df = pd.read_sql_query("""
        WITH latest AS (
            SELECT problem_id,
                   MAX(attempt_date) AS last_attempt_date,
                   bucket
            FROM (
                SELECT pa.problem_id, pa.attempt_date, pa.bucket,
                       ROW_NUMBER() OVER (PARTITION BY pa.problem_id ORDER BY pa.attempt_date DESC, pa.attempt_id DESC) AS rn
                FROM problem_attempts pa
            )
            WHERE rn = 1
            GROUP BY problem_id
        )
        SELECT p.problem_id, p.leetcode_number, p.title, p.link,
               l.bucket, l.last_attempt_date
        FROM problems p
        LEFT JOIN latest l ON p.problem_id = l.problem_id
    """, conn)
    conn.close()

    today = date.today().isoformat()
    df["last_attempt_date"] = df["last_attempt_date"].fillna("1970-01-01")
    df["days_since"] = (
        pd.to_datetime(today) - pd.to_datetime(df["last_attempt_date"])
    ).dt.days
    df["bucket"] = df["bucket"].fillna("Learning")
    return df


def pick_problem(bucket: str, top_n: int = 5) -> dict | None:
    """
    Pick a random problem from the top_n oldest-attempted problems in the given bucket.
    Returns None if no problems exist in that bucket.
    """
    df = get_problems_with_current_bucket()
    filtered = df[df["bucket"] == bucket].copy()
    if filtered.empty:
        return None

    filtered = filtered.sort_values("days_since", ascending=False)
    candidates = filtered.head(top_n)
    chosen = candidates.sample(1).iloc[0]
    return chosen.to_dict()
