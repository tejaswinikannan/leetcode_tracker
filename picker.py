"""
picker.py  —  Multi-factor smart problem picker

Scoring model (higher score = higher priority):
  ┌─────────────────────────┬────────┬─────────────────────────────────────────┐
  │ Factor                  │ Weight │ Logic                                   │
  ├─────────────────────────┼────────┼─────────────────────────────────────────┤
  │ Recency                 │  25%   │ days since last attempt, capped at 60   │
  │ Last result             │  35%   │ failed=10, partial=5, solved=0          │
  │ Historical failure rate │  25%   │ % of all attempts that were failures    │
  │ Avg solve time          │  15%   │ normalised across all problems           │
  └─────────────────────────┴────────┴─────────────────────────────────────────┘

Each factor is normalised to [0, 1] before weighting so they're comparable.
The final score is in [0, 1] — higher means "needs more attention".
"""

import random
from datetime import date
import pandas as pd
from database import get_connection

# ── Weights (must sum to 1.0) ────────────────────────────────────────────────
W_RECENCY      = 0.25
W_LAST_RESULT  = 0.35
W_FAIL_RATE    = 0.25
W_SOLVE_TIME   = 0.15

RESULT_PENALTY = {"failed": 1.0, "partial": 0.5, "solved": 0.0}
RECENCY_CAP    = 60   # days — anything older than this gets max recency score


def get_problems_with_current_bucket() -> pd.DataFrame:
    """
    Returns one row per problem with its latest bucket and last attempt date.
    """
    conn = get_connection()
    df = pd.read_sql_query("""
        WITH ranked AS (
            SELECT pa.problem_id,
                   pa.attempt_date,
                   pa.bucket,
                   pa.attempt_id,
                   ROW_NUMBER() OVER (
                       PARTITION BY pa.problem_id
                       ORDER BY pa.attempt_date DESC, pa.attempt_id DESC
                   ) AS rn
            FROM problem_attempts pa
        )
        SELECT p.problem_id, p.leetcode_number, p.title, p.link,
               r.bucket, r.attempt_date AS last_attempt_date
        FROM problems p
        LEFT JOIN ranked r ON p.problem_id = r.problem_id AND r.rn = 1
    """, conn)
    conn.close()

    today = date.today().isoformat()
    df["last_attempt_date"] = df["last_attempt_date"].fillna("1970-01-01")
    df["days_since"] = (
        pd.to_datetime(today) - pd.to_datetime(df["last_attempt_date"])
    ).dt.days
    df["bucket"] = df["bucket"].fillna("Learning")
    return df


def _get_attempt_stats() -> pd.DataFrame:
    """
    Per-problem aggregate stats across all historical attempts:
      - total_attempts
      - fail_count
      - partial_count
      - solve_count
      - failure_rate       (fail_count / total)
      - avg_solve_time     (minutes, NaN if never recorded)
      - last_result        (result of most recent attempt)
    """
    conn = get_connection()
    df = pd.read_sql_query("""
        SELECT problem_id, result, solve_time,
               ROW_NUMBER() OVER (
                   PARTITION BY problem_id
                   ORDER BY attempt_date DESC, attempt_id DESC
               ) AS rn
        FROM problem_attempts
    """, conn)
    conn.close()

    if df.empty:
        return pd.DataFrame(columns=[
            "problem_id", "total_attempts", "fail_count", "partial_count",
            "solve_count", "failure_rate", "avg_solve_time", "last_result"
        ])

    last_result = df[df["rn"] == 1][["problem_id", "result"]].rename(
        columns={"result": "last_result"}
    )

    agg = df.groupby("problem_id").agg(
        total_attempts=("result", "count"),
        fail_count    =("result", lambda x: (x == "failed").sum()),
        partial_count =("result", lambda x: (x == "partial").sum()),
        solve_count   =("result", lambda x: (x == "solved").sum()),
        avg_solve_time=("solve_time", "mean"),
    ).reset_index()

    agg["failure_rate"] = agg["fail_count"] / agg["total_attempts"]
    agg = agg.merge(last_result, on="problem_id", how="left")
    return agg


def _normalise(series: pd.Series) -> pd.Series:
    """Min-max normalise a series to [0, 1]. Handles zero-range gracefully."""
    lo, hi = series.min(), series.max()
    if hi == lo:
        return pd.Series([0.5] * len(series), index=series.index)
    return (series - lo) / (hi - lo)


def compute_scores(bucket: str) -> pd.DataFrame:
    """
    Returns a DataFrame of all problems in `bucket` with individual factor
    scores and a final weighted score. Sorted by score descending.
    """
    base = get_problems_with_current_bucket()
    filtered = base[base["bucket"] == bucket].copy()
    if filtered.empty:
        return pd.DataFrame()

    stats = _get_attempt_stats()
    df = filtered.merge(stats, on="problem_id", how="left")

    # ── Factor 1: Recency ────────────────────────────────────────────────────
    df["days_capped"] = df["days_since"].clip(upper=RECENCY_CAP)
    df["score_recency"] = _normalise(df["days_capped"])

    # ── Factor 2: Last result penalty ───────────────────────────────────────
    df["last_result"] = df["last_result"].fillna("failed")   # never attempted = treat as failed
    df["result_raw"]  = df["last_result"].map(RESULT_PENALTY).fillna(0.5)
    df["score_last_result"] = df["result_raw"]               # already in [0,1]

    # ── Factor 3: Historical failure rate ───────────────────────────────────
    df["failure_rate"]      = df["failure_rate"].fillna(1.0) # no history = assume hard
    df["score_fail_rate"]   = df["failure_rate"]             # already in [0,1]

    # ── Factor 4: Avg solve time ─────────────────────────────────────────────
    # Fill missing with median of known times; if all missing use 0
    median_time = df["avg_solve_time"].median()
    if pd.isna(median_time):
        median_time = 0
    df["avg_solve_time_filled"] = df["avg_solve_time"].fillna(median_time)
    df["score_solve_time"]      = _normalise(df["avg_solve_time_filled"])

    # ── Weighted final score ─────────────────────────────────────────────────
    df["score"] = (
        W_RECENCY     * df["score_recency"]     +
        W_LAST_RESULT * df["score_last_result"] +
        W_FAIL_RATE   * df["score_fail_rate"]   +
        W_SOLVE_TIME  * df["score_solve_time"]
    )

    df = df.sort_values("score", ascending=False).reset_index(drop=True)
    return df


def pick_problem(bucket: str, top_n: int = 5, exclude_id: int | None = None) -> dict | None:
    """
    Pick a problem using multi-factor scoring.
    - Scores all problems in the bucket
    - Takes top_n candidates
    - Randomly selects one (weighted by score so higher-scored problems
      are more likely but not guaranteed)
    - Optionally excludes a problem_id (to avoid back-to-back repeats)

    Returns the chosen row as a dict, or None if bucket is empty.
    """
    df = compute_scores(bucket)
    if df.empty:
        return None

    if exclude_id is not None:
        df = df[df["problem_id"] != exclude_id]
        if df.empty:
            df = compute_scores(bucket)  # only one problem, ignore exclusion

    candidates = df.head(top_n).copy()

    # Weighted random: normalise scores within candidates so they sum to 1
    total = candidates["score"].sum()
    if total == 0:
        weights = None  # uniform
    else:
        weights = candidates["score"] / total

    chosen = candidates.sample(1, weights=weights).iloc[0]
    return chosen.to_dict()