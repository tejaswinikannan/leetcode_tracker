"""
config.py — Persist LeetCode credentials locally in a .env-style JSON file.
Stored in the same directory as the app, gitignored by default.
"""

import json
import os

CONFIG_PATH = os.path.join(os.path.dirname(__file__), ".lc_config.json")


def load_config() -> dict:
    if not os.path.exists(CONFIG_PATH):
        return {"username": "", "session": "", "csrf": ""}
    try:
        with open(CONFIG_PATH, "r") as f:
            return json.load(f)
    except Exception:
        return {"username": "", "session": "", "csrf": ""}


def save_config(username: str, session: str, csrf: str):
    with open(CONFIG_PATH, "w") as f:
        json.dump({"username": username, "session": session, "csrf": csrf}, f)


def clear_config():
    if os.path.exists(CONFIG_PATH):
        os.remove(CONFIG_PATH)


def config_exists() -> bool:
    cfg = load_config()
    return bool(cfg.get("username") and cfg.get("session") and cfg.get("csrf"))
