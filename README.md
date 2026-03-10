# LeetCode Practice Tracker

A lightweight personal tool for tracking LeetCode problems, logging every attempt, and getting smart practice recommendations based on your history.

## Why I Built This

LeetCode has no built-in way to track how you're actually progressing on individual problems over time. You solve something, move on, and forget about it. A few weeks later you attempt it again and realize you've lost the intuition entirely.

This tool fixes that by keeping a full history of every attempt — not just whether you've solved a problem, but how long it took, whether you failed it before, and how long it's been since you last touched it. That history then drives a smarter practice picker that decides what you should revisit next.

## Tech Stack

- **Python** — core language
- **SQLite** — local database, no server required, single file on disk
- **Streamlit** — UI framework for building the web interface in Python
- **Pandas** — data wrangling for scoring and analytics

## Architecture

The app is split into 3 modules:

**`database.py`** handles all SQLite interactions. There are two tables — `problems` for static problem metadata (number, title, link) and `problem_attempts` for every attempt ever logged. Attempts are append-only, meaning nothing is ever updated or deleted. Each attempt is a new row with its own date, bucket, result, solve time, and notes.

**`picker.py`** contains the smart recommendation logic. When you ask for a problem, it scores every problem in the selected bucket across four factors — how long since you last attempted it, what your last result was (failed/partial/solved), your historical failure rate on that problem, and your average solve time. Each factor is normalized to a 0–1 scale and combined into a weighted score. The top 5 by score become candidates, and one is picked at random weighted by score so higher-priority problems are more likely but not guaranteed. The last picked problem is excluded to prevent back-to-back repeats.

**`leetcode_sync.py`** handles automatic importing from LeetCode. It calls LeetCode's GraphQL API using your session cookies, fetches recent accepted submissions, and adds any new ones to a queue. From there you manually review each queued item, set the bucket and result, and import it — keeping you in control of the data rather than auto-importing everything blindly.

## Database Design

The append-only event log is the core design decision. Rather than storing a single "current state" per problem, every attempt is recorded as a new row. This means the current bucket for a problem is always derived from its most recent attempt, not stored directly. It also means the full history is always available for analytics without any data being lost to updates.

```
problems
  problem_id, leetcode_number, title, link, created_date
