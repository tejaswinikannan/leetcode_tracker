"""
picker.py  —  ML-based smart problem picker

Scores every problem by predicting P(next attempt needs attention) — i.e. the
probability the next attempt on that problem would be "failed" or "partial"
rather than "solved" — using an XGBoost classifier trained fresh on your
attempt history each time this runs. See notebooks/model_comparison.ipynb for
the model comparison (Logistic Regression vs. Decision Tree vs. XGBoost) that
led to this choice, including the pattern-tag features. XGBoost shipped even
though a single Decision Tree scored higher AUC on that notebook's held-out
split (0.779 vs 0.715) — see its Takeaways section for why: the test set is
tiny (53 rows, one time-based split, no cross-validation) and the tree's
feature importances suggest it overfit to that split rather than learning a
generalizable rule, whereas XGBoost's importances were far more evenly spread.

  Challenge Mode  — top tier    (P(needs_attention) >= 0.50)
  Steady Grind    — middle tier (0.25–0.50)
  Chill Mode      — bottom tier (< 0.25)

Falls back to a simple hand-weighted heuristic when there isn't enough
attempt history yet to train a reliable model (cold start).

Problems tagged with a pattern in EXCLUDED_PATTERNS (currently just SQL) are
kept out of training and never scored/picked — SQL attempts caused
quasi-separation (every SQL attempt had the same outcome), which made the
model overconfident. Their data stays in the database untouched; they just
don't participate in the picker.
"""

import random
from datetime import date
import pandas as pd
from xgboost import XGBClassifier
from database import get_connection

MIN_ATTEMPTS_FOR_MODEL = 30  # below this, fall back to the heuristic

# ── Fallback heuristic weights (used only on cold start) ────────────────────
W_LAST_RESULT  = 0.30
W_FAIL_RATE    = 0.25
W_DIFFICULTY   = 0.25
W_RECENCY      = 0.15
W_SOLVE_TIME   = 0.05

RESULT_PENALTY    = {"failed": 1.0, "partial": 0.5, "solved": 0.0}
DIFFICULTY_SCORE  = {"Hard": 1.0, "Medium": 0.5, "Easy": 0.0}
RECENCY_CAP       = 60  # days
SOLVE_TIME_THRESHOLDS = {"Easy": 10, "Medium": 15, "Hard": 30}

# ── Mode score thresholds (apply to both the model's probability and the
#    heuristic's [0,1] score) ─────────────────────────────────────────────
MODE_THRESHOLDS = {
    "challenge": (0.51, 1.01),   # top tier
    "grind":     (0.25, 0.50),   # mid tier
    "chill":     (0.00, 0.25),   # bottom tier
}

# Patterns excluded from model training AND from being picked/scored at all —
# not removed from the database, just kept out of the ML pipeline. SQL problems
# caused quasi-separation (every SQL attempt had the same outcome), producing
# unreliable, overconfident scores (see notebooks/model_comparison.ipynb).
EXCLUDED_PATTERNS = ["SQL"]

NUMERIC_FEATURES = [
    "days_since_last_attempt", "prior_attempt_count", "prior_failure_rate",
    "prior_avg_solve_time", "is_first_attempt", "solve_time_missing",
]
CATEGORICAL_FEATURES = ["difficulty", "prior_bucket", "pattern"]


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
               p.difficulty, p.pattern, r.bucket, r.attempt_date AS last_attempt_date
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
    df["pattern"]     = df["pattern"].fillna("Unknown")
    return df


def _get_attempt_stats() -> pd.DataFrame:
    """Per-problem aggregate stats across all historical attempts (as of now)."""
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


def _load_raw_attempts() -> pd.DataFrame:
    """All attempts joined with problem metadata, for training-frame construction."""
    conn = get_connection()
    df = pd.read_sql_query("""
        SELECT pa.attempt_id, pa.problem_id, pa.attempt_date, pa.bucket, pa.result, pa.solve_time,
               p.difficulty, p.created_date, p.pattern
        FROM problem_attempts pa
        JOIN problems p ON pa.problem_id = p.problem_id
    """, conn)
    conn.close()
    return df


def _build_training_frame():
    """
    Leakage-free per-attempt feature table + target, mirroring
    notebooks/model_comparison.ipynb: every feature is computed from only
    what was known *before* that attempt.
    """
    df = _load_raw_attempts()
    df = df[~df["pattern"].isin(EXCLUDED_PATTERNS)]
    if df.empty:
        return pd.DataFrame(), pd.Series(dtype=int)

    df["attempt_date"] = pd.to_datetime(df["attempt_date"])
    df["created_date"]  = pd.to_datetime(df["created_date"])
    df = df.sort_values(["problem_id", "attempt_date", "attempt_id"]).reset_index(drop=True)

    df["is_fail"] = df["result"].isin(["failed", "partial"]).astype(int)
    grp = df.groupby("problem_id")

    df["prior_attempt_count"] = grp.cumcount()
    df["prior_fail_count"]    = grp["is_fail"].cumsum() - df["is_fail"]
    df["prior_failure_rate"]  = (df["prior_fail_count"] / df["prior_attempt_count"]).fillna(0.5)
    df["is_first_attempt"]    = (df["prior_attempt_count"] == 0).astype(int)

    df["prior_avg_solve_time"] = (
        grp["solve_time"].apply(lambda s: s.shift(1).expanding().mean())
          .reset_index(level=0, drop=True)
    )
    median_solve_time = df["solve_time"].median()
    df["solve_time_missing"]   = df["prior_avg_solve_time"].isna().astype(int)
    df["prior_avg_solve_time"] = df["prior_avg_solve_time"].fillna(median_solve_time if pd.notna(median_solve_time) else 0)

    df["prior_bucket"] = grp["bucket"].shift(1).fillna("Learning")

    prev_date = grp["attempt_date"].shift(1)
    df["days_since_last_attempt"] = (df["attempt_date"] - prev_date).dt.days
    fallback_days = (df["attempt_date"] - df["created_date"]).dt.days
    df["days_since_last_attempt"] = df["days_since_last_attempt"].fillna(fallback_days).clip(lower=0)

    df["pattern"] = df["pattern"].fillna("Unknown")

    X = df[NUMERIC_FEATURES + CATEGORICAL_FEATURES].copy()
    X = pd.get_dummies(X, columns=CATEGORICAL_FEATURES, drop_first=True)
    y = df["is_fail"]
    return X, y


def _build_prediction_frame(feature_columns, base: pd.DataFrame, stats: pd.DataFrame):
    """Current-state features for every tracked problem, aligned to the trained model's columns."""
    df = base.merge(stats, on="problem_id", how="left")

    df["prior_attempt_count"] = df["total_attempts"].fillna(0)
    df["prior_failure_rate"]  = df["failure_rate"].fillna(0.5)
    df["is_first_attempt"]    = (df["prior_attempt_count"] == 0).astype(int)

    median_solve_time = df["avg_solve_time"].median()
    df["solve_time_missing"]   = df["avg_solve_time"].isna().astype(int)
    df["prior_avg_solve_time"] = df["avg_solve_time"].fillna(median_solve_time if pd.notna(median_solve_time) else 0)

    df["prior_bucket"]            = df["bucket"]  # current bucket = state going into the next attempt
    df["days_since_last_attempt"] = df["days_since"]

    X = df[["problem_id"] + NUMERIC_FEATURES + CATEGORICAL_FEATURES].copy()
    X = pd.get_dummies(X, columns=CATEGORICAL_FEATURES, drop_first=True)
    problem_ids = X["problem_id"]
    X = X.drop(columns=["problem_id"]).reindex(columns=feature_columns, fill_value=0)
    return problem_ids, X


def _heuristic_scores(df: pd.DataFrame) -> pd.Series:
    """Fallback scoring when there isn't enough history to train a model."""
    score_last_result = df["last_result"].map(RESULT_PENALTY).fillna(0.5)
    score_fail_rate    = df["failure_rate"]
    score_difficulty   = df["difficulty"].map(DIFFICULTY_SCORE).fillna(0.5)

    days_capped = df["days_since"].clip(upper=RECENCY_CAP)
    lo, hi = days_capped.min(), days_capped.max()
    score_recency = pd.Series([0.5] * len(df), index=df.index) if hi == lo else (days_capped - lo) / (hi - lo)

    median_time = df["avg_solve_time"].median()
    median_time = 0 if pd.isna(median_time) else median_time
    avg_solve_time_filled = df["avg_solve_time"].fillna(median_time)
    time_threshold = df["difficulty"].map(SOLVE_TIME_THRESHOLDS).fillna(30)
    score_solve_time = (avg_solve_time_filled > time_threshold).astype(float)

    return (
        W_LAST_RESULT * score_last_result +
        W_FAIL_RATE   * score_fail_rate   +
        W_DIFFICULTY  * score_difficulty  +
        W_RECENCY     * score_recency     +
        W_SOLVE_TIME  * score_solve_time
    )


def compute_scores() -> pd.DataFrame:
    """
    Score ALL problems globally by predicted P(needs attention), using a
    freshly-trained XGBoost model (or the heuristic fallback on cold start).
    Returns a DataFrame sorted by score descending, with a 'mode' column
    indicating which tier each problem falls into.
    """
    base = get_problems_with_current_bucket()
    if base.empty:
        return pd.DataFrame()

    base = base[~base["pattern"].isin(EXCLUDED_PATTERNS)].reset_index(drop=True)
    if base.empty:
        return pd.DataFrame()

    stats = _get_attempt_stats()
    df = base.merge(stats, on="problem_id", how="left")
    df["last_result"]  = df["last_result"].fillna("failed")   # never attempted = treat as failed
    df["failure_rate"] = df["failure_rate"].fillna(1.0)       # no history = assume hard

    X_train, y_train = _build_training_frame()

    if len(X_train) < MIN_ATTEMPTS_FOR_MODEL or y_train.nunique() < 2:
        df["score"] = _heuristic_scores(df)
    else:
        model = XGBClassifier(
            n_estimators=100, max_depth=3, learning_rate=0.1,
            subsample=0.8, colsample_bytree=0.8,
            eval_metric="logloss", random_state=42,
        )
        model.fit(X_train, y_train)

        problem_ids, X_pred = _build_prediction_frame(list(X_train.columns), base, stats)
        proba = model.predict_proba(X_pred)[:, 1]
        scores = pd.DataFrame({"problem_id": problem_ids.values, "score": proba})
        df = df.merge(scores, on="problem_id", how="left")
        df["score"] = df["score"].fillna(df["failure_rate"])  # per-row safety net

    def _mode(score):
        if score >= 0.50:   return "challenge"
        elif score >= 0.25: return "grind"
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
