"""
picker.py  —  Multi-factor smart problem picker

Every problem is scored globally across five factors. The final score
determines which mode the problem falls into:

  Challenge Mode  — top tier    (score >= 0.67)
  Steady Grind    — middle tier (score 0.33–0.67)
  Chill Mode      — bottom tier (score < 0.33)

Scoring factors (higher score = needs more attention):
  ┌──────────────────────────┬────────┬────────────────────────────────────────┐
  │ Factor                   │ Weight │ Logic                                  │
  ├──────────────────────────┼────────┼────────────────────────────────────────┤
  │ Last result              │  30%   │ failed=1.0, partial=0.5, solved=0.0   │
  │ Historical failure rate  │  25%   │ fail_count / total_attempts            │
  │ Difficulty               │  20%   │ Hard=1.0, Medium=0.5, Easy=0.0        │
  │ Recency                  │  15%   │ days since last attempt, capped at 60  │
  │ Avg solve time           │  10%   │ 1.0 if exceeds threshold (Easy:15m,    │
  │                          │        │ Medium:30m, Hard:40m), else 0.0        │
  └──────────────────────────┴────────┴────────────────────────────────────────┘

Each factor normalised to [0, 1] before weighting.
Final score in [0, 1] — higher = needs more attention / more challenging.
"""

import random
from datetime import date
import pandas as pd
from database import get_connection

# ── Weights (must sum to 1.0) ────────────────────────────────────────────────
W_LAST_RESULT  = 0.30
W_FAIL_RATE    = 0.25
W_DIFFICULTY   = 0.20
W_RECENCY      = 0.15
W_SOLVE_TIME   = 0.10

RESULT_PENALTY    = {"failed": 1.0, "partial": 0.5, "solved": 0.0}
DIFFICULTY_SCORE  = {"Hard": 1.0, "Medium": 0.5, "Easy": 0.0}
RECENCY_CAP       = 60  # days

# ── Solve time thresholds (minutes) ─────────────────────────────────────────
SOLVE_TIME_THRESHOLDS = {"Easy": 10, "Medium": 15, "Hard": 30}

# ── Mode score thresholds ────────────────────────────────────────────────────
MODE_THRESHOLDS = {
    "challenge": (0.50, 1.01),   # top tier
    "grind":     (0.30, 0.50),   # mid tier
    "chill":     (0.00, 0.30),   # bottom tier
}


def get_problems_with_current_bucket() -> pd.DataFrame:
    """Returns one row per problem with its latest bucket and last attempt date."""
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
               p.difficulty, r.bucket, r.attempt_date AS last_attempt_date
        FROM problems p
        LEFT JOIN ranked r ON p.problem_id = r.problem_id AND r.rn = 1
    """, conn)
    conn.close()

    today = date.today().isoformat()
    df["last_attempt_date"] = df["last_attempt_date"].fillna("1970-01-01")
    df["days_since"] = (
        pd.to_datetime(today) - pd.to_datetime(df["last_attempt_date"])
    ).dt.days
    df["bucket"]     = df["bucket"].fillna("Learning")
    df["difficulty"] = df["difficulty"].fillna("Medium")
    return df


def _get_attempt_stats() -> pd.DataFrame:
    """Per-problem aggregate stats across all historical attempts."""
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
            "problem_id", "total_attempts", "fail_count",
            "failure_rate", "avg_solve_time", "last_result"
        ])

    last_result = (
        df[df["rn"] == 1][["problem_id", "result"]]
        .rename(columns={"result": "last_result"})
    )

    agg = df.groupby("problem_id").agg(
        total_attempts=("result", "count"),
        fail_count    =("result", lambda x: (x == "failed").sum()),
        avg_solve_time=("solve_time", "mean"),
    ).reset_index()

    agg["failure_rate"] = agg["fail_count"] / agg["total_attempts"]
    agg = agg.merge(last_result, on="problem_id", how="left")
    return agg


def _normalise(series: pd.Series) -> pd.Series:
    """Min-max normalise to [0, 1]. Returns 0.5 for zero-range series."""
    lo, hi = series.min(), series.max()
    if hi == lo:
        return pd.Series([0.5] * len(series), index=series.index)
    return (series - lo) / (hi - lo)


def compute_scores() -> pd.DataFrame:
    """
    Score ALL problems globally across all five factors.
    Returns a DataFrame sorted by score descending, with a 'mode' column
    indicating which tier each problem falls into.
    """
    base  = get_problems_with_current_bucket()
    if base.empty:
        return pd.DataFrame()

    stats = _get_attempt_stats()
    df    = base.merge(stats, on="problem_id", how="left")

    # ── Factor 1: Last result ────────────────────────────────────────────────
    df["last_result"]       = df["last_result"].fillna("failed")  # never attempted = treat as failed
    df["score_last_result"] = df["last_result"].map(RESULT_PENALTY).fillna(0.5)

    # ── Factor 2: Historical failure rate ────────────────────────────────────
    df["failure_rate"]    = df["failure_rate"].fillna(1.0)        # no history = assume hard
    df["score_fail_rate"] = df["failure_rate"]                    # already [0,1]

    # ── Factor 3: Difficulty ─────────────────────────────────────────────────
    df["score_difficulty"] = df["difficulty"].map(DIFFICULTY_SCORE).fillna(0.5)

    # ── Factor 4: Recency ────────────────────────────────────────────────────
    df["days_capped"]   = df["days_since"].clip(upper=RECENCY_CAP)
    df["score_recency"] = _normalise(df["days_capped"])

    # ── Factor 5: Avg solve time ─────────────────────────────────────────────
    median_time = df["avg_solve_time"].median()
    if pd.isna(median_time):
        median_time = 0
    df["avg_solve_time_filled"] = df["avg_solve_time"].fillna(median_time)
    df["time_threshold"] = df["difficulty"].map(SOLVE_TIME_THRESHOLDS).fillna(30)  # default to Medium
    df["score_solve_time"] = (df["avg_solve_time_filled"] > df["time_threshold"]).astype(float)

    # ── Weighted final score ─────────────────────────────────────────────────
    df["score"] = (
        W_LAST_RESULT * df["score_last_result"] +
        W_FAIL_RATE   * df["score_fail_rate"]   +
        W_DIFFICULTY  * df["score_difficulty"]  +
        W_RECENCY     * df["score_recency"]     +
        W_SOLVE_TIME  * df["score_solve_time"]
    )

    # ── Assign mode tier ─────────────────────────────────────────────────────
    def _mode(score):
        if score >= 0.67:   return "challenge"
        elif score >= 0.33: return "grind"
        else:               return "chill"

    df["mode"] = df["score"].apply(_mode)
    df = df.sort_values("score", ascending=False).reset_index(drop=True)
    return df


def pick_problem(mode: str, top_n: int = 5, exclude_id: int | None = None) -> dict | None:
    """
    Pick a problem for the given mode ('challenge', 'grind', 'chill').

    - Scores all problems globally
    - Filters to the mode's score tier
    - Takes top_n candidates by score
    - Weighted random pick within those candidates
    - Excludes last picked problem to prevent back-to-back repeats

    Returns chosen row as dict, or None if no problems fall in that tier.
    """
    df = compute_scores()
    if df.empty:
        return None

    filtered = df[df["mode"] == mode].copy()

    # Fallback: if the tier is empty (e.g. all problems score very high),
    # relax to nearest adjacent tier
    if filtered.empty:
        if mode == "challenge":
            filtered = df.head(max(1, len(df) // 3)).copy()
        elif mode == "chill":
            filtered = df.tail(max(1, len(df) // 3)).copy()
        else:
            mid = len(df) // 3
            filtered = df.iloc[mid: mid * 2].copy()

    if exclude_id is not None and len(filtered) > 1:
        filtered = filtered[filtered["problem_id"] != exclude_id]

    candidates = filtered.head(top_n).copy()

    total = candidates["score"].sum()
    weights = candidates["score"] / total if total > 0 else None

    chosen = candidates.sample(1, weights=weights).iloc[0]
    return chosen.to_dict()