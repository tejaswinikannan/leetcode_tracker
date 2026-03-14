import streamlit as st
from datetime import date, datetime

import database as db
import picker as pk
import leetcode_sync as sync
import config as cfg

# ── Init ────────────────────────────────────────────────────────────────────
db.init_db()
sync.init_sync_table()

# ── Page config ─────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="LeetCode Tracker",
    page_icon="⚡",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── CSS ─────────────────────────────────────────────────────────────────────
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@400;600;700&family=Space+Grotesk:wght@300;400;500;600;700&display=swap');

html, body, [class*="css"] {
    font-family: 'Space Grotesk', sans-serif;
    background-color: #0d1117;
    color: #e6edf3;
}
section[data-testid="stSidebar"] {
    background: #010409 !important;
    border-right: 1px solid #21262d;
}

/* Kill ALL gaps between sidebar elements */
section[data-testid="stSidebar"] [data-testid="stVerticalBlock"] {
    gap: 0rem !important;
}
section[data-testid="stSidebar"] .stButton {
    margin-bottom: 0 !important;
}
section[data-testid="stSidebar"] .stButton > button {
    margin: 0 !important;
    padding: 0.38rem 0.85rem !important;
    background: transparent !important;
    border: none !important;
    border-left: 3px solid transparent !important;
    border-radius: 0 !important;
    color: #6e7681 !important;
    font-family: 'Space Grotesk', sans-serif !important;
    font-size: 0.88rem !important;
    font-weight: 400 !important;
    text-align: left !important;
    width: 100% !important;
    transition: background 0.15s, color 0.15s !important;
    box-shadow: none !important;
    line-height: 1.5 !important;
}
section[data-testid="stSidebar"] .stButton > button:hover {
    background: #161b22 !important;
    color: #e6edf3 !important;
    border-left: 3px solid #30363d !important;
    border-radius: 0 !important;
}
section[data-testid="stSidebar"] .stButton > button:focus:not(:active) {
    background: #1a2332 !important;
    border-left: 3px solid #58a6ff !important;
    color: #58a6ff !important;
    font-weight: 600 !important;
}
.page-header {
    background: linear-gradient(135deg, #161b22 0%, #0d1117 100%);
    border: 1px solid #21262d;
    border-radius: 12px;
    padding: 1.5rem 2rem;
    margin-bottom: 2rem;
}
.page-header h1 { font-family: 'JetBrains Mono', monospace; font-size: 1.5rem; color: #58a6ff; margin: 0 0 0.25rem 0; }
.page-header p  { color: #8b949e; margin: 0; font-size: 0.9rem; }

.metric-card { background: #161b22; border: 1px solid #21262d; border-radius: 10px; padding: 1.2rem 1.5rem; text-align: center; }
.metric-card .value { font-family: 'JetBrains Mono', monospace; font-size: 2.2rem; font-weight: 700; line-height: 1; margin-bottom: 0.3rem; }
.metric-card .label { font-size: 0.78rem; color: #8b949e; text-transform: uppercase; letter-spacing: 1px; }

.badge { display: inline-block; padding: 3px 10px; border-radius: 20px; font-size: 0.75rem; font-weight: 600; letter-spacing: 0.5px; font-family: 'JetBrains Mono', monospace; }
.badge-learning   { background: #7c2d12; color: #fdba74; border: 1px solid #9a3412; }
.badge-practicing { background: #1e3a5f; color: #93c5fd; border: 1px solid #1d4ed8; }
.badge-mastered   { background: #14532d; color: #86efac; border: 1px solid #15803d; }
.badge-easy   { background: #14532d; color: #86efac; border: 1px solid #15803d; }
.badge-medium { background: #451a03; color: #fcd34d; border: 1px solid #92400e; }
.badge-hard   { background: #450a0a; color: #fca5a5; border: 1px solid #991b1b; }

.pick-card { background: linear-gradient(135deg, #161b22 0%, #0d1117 100%); border: 1px solid #30363d; border-radius: 16px; padding: 2rem 2.5rem; margin: 1rem 0; position: relative; overflow: hidden; }
.pick-card::before { content: ''; position: absolute; top: 0; left: 0; right: 0; height: 3px; background: linear-gradient(90deg, #58a6ff, #3b82f6, #00b4d8); }
.pick-card .problem-num  { font-family: 'JetBrains Mono', monospace; font-size: 0.85rem; color: #58a6ff; margin-bottom: 0.4rem; }
.pick-card .problem-title { font-size: 1.6rem; font-weight: 700; color: #e6edf3; margin-bottom: 0.8rem; }
.pick-card .meta { font-size: 0.82rem; color: #8b949e; }

.queue-card { background: #161b22; border: 1px solid #21262d; border-radius: 10px; padding: 1.1rem 1.4rem; margin-bottom: 0.75rem; }
.queue-card .qnum  { font-family: 'JetBrains Mono', monospace; font-size: 0.82rem; color: #58a6ff; }
.queue-card .qtitle { font-size: 1rem; font-weight: 600; color: #e6edf3; margin: 0.2rem 0 0.5rem 0; }
.queue-card .qmeta  { font-size: 0.8rem; color: #484f58; }

.info-box { background: #161b22; border: 1px solid #21262d; border-radius: 10px; padding: 1.25rem 1.5rem; }

.stTextInput input, .stNumberInput input, .stTextArea textarea { background: #161b22 !important; border: 1px solid #30363d !important; color: #e6edf3 !important; border-radius: 8px !important; font-family: 'Space Grotesk', sans-serif !important; }
.stTextInput input:focus, .stNumberInput input:focus { border-color: #58a6ff !important; }
.stButton button { background: #21262d !important; color: #e6edf3 !important; border: 1px solid #30363d !important; border-radius: 8px !important; font-family: 'Space Grotesk', sans-serif !important; font-weight: 500 !important; }
.stButton button:hover { background: #30363d !important; border-color: #58a6ff !important; color: #58a6ff !important; }
.stButton button[kind="primary"] { background: #1f6feb !important; border-color: #388bfd !important; color: white !important; }
div[data-baseweb="select"] > div { background: #161b22 !important; border-color: #30363d !important; color: #e6edf3 !important; border-radius: 8px !important; }
.problem-row { background: #161b22; border: 1px solid #21262d; border-radius: 8px; padding: 0.9rem 1.2rem; margin-bottom: 0.5rem; display: flex; align-items: center; justify-content: space-between; }
.problem-row .num   { font-family: 'JetBrains Mono', monospace; color: #58a6ff; font-size: 0.85rem; min-width: 60px; }
.problem-row .title { font-weight: 500; flex: 1; padding: 0 1rem; }
.attempt-row { background: #0d1117; border-left: 3px solid #21262d; border-radius: 0 6px 6px 0; padding: 0.6rem 1rem; margin: 0.3rem 0; font-size: 0.88rem; color: #8b949e; }
.section-label { font-size: 0.72rem; font-weight: 600; text-transform: uppercase; letter-spacing: 1.5px; color: #484f58; margin-bottom: 0.75rem; margin-top: 1.5rem; }
#MainMenu, footer, header { visibility: hidden; }
</style>
""", unsafe_allow_html=True)


# ── Session state defaults — load from saved config if available ─────────────
_saved = cfg.load_config()
if "lc_username" not in st.session_state: st.session_state["lc_username"] = _saved.get("username", "")
if "lc_session"  not in st.session_state: st.session_state["lc_session"]  = _saved.get("session", "")
if "lc_csrf"     not in st.session_state: st.session_state["lc_csrf"]     = _saved.get("csrf", "")
if "page"        not in st.session_state: st.session_state["page"]        = "🏠  Dashboard"

# Clear stale picked state from old bucket-based system
if "picked_bucket" in st.session_state:
    del st.session_state["picked_bucket"]
    st.session_state.pop("picked", None)

NAV_ITEMS = [
    "🏠  Dashboard",
    "🔄  Sync from LeetCode",
    "📥  Import Queue",
    "➕  Add Problem",
    "🎯  Pick Problem",
    "📝  Log Attempt",
    # "📊  Analytics",
]

# ── Sidebar ──────────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("""
    <div style="padding:1rem 0 1rem 0;">
        <div style="font-family:'JetBrains Mono',monospace;font-size:1.1rem;color:#58a6ff;font-weight:700;">⚡ LeetCode Tracker</div>
      </div>
    """, unsafe_allow_html=True)

    # Inject per-button active CSS based on current page
    active_page = st.session_state["page"]
    active_key  = f"nav_{active_page}"
    st.markdown(f"""
    <style>
    [data-testid="stSidebar"] [key="{active_key}"] button,
    [data-testid="stSidebar"] button[kind="secondary"][data-testid="{active_key}"] {{
        background: #1a2332 !important;
        border-left: 3px solid #58a6ff !important;
        color: #58a6ff !important;
        font-weight: 600 !important;
    }}
    /* Target active button by aria-label as fallback */
    [data-testid="stSidebar"] .stButton:has(button[aria-label="{active_page}"]) button {{
        background: #1a2332 !important;
        border-left: 3px solid #58a6ff !important;
        color: #58a6ff !important;
        font-weight: 600 !important;
    }}
    </style>
    """, unsafe_allow_html=True)

    for item in NAV_ITEMS:
        if st.button(item, key=f"nav_{item}", use_container_width=True):
            st.session_state["page"] = item
            st.rerun()

    page = st.session_state["page"]

    problems = db.get_all_problems()
    attempts = db.get_all_attempts()
    qcounts  = sync.get_queue_counts()
    pending  = qcounts.get("pending") or 0

    st.markdown("---")
    st.markdown(f"""
    <div style="font-size:0.75rem;color:#484f58;text-transform:uppercase;letter-spacing:1px;margin-bottom:0.5rem;">Quick Stats</div>
    <div style="font-size:0.88rem;color:#8b949e;">
        🗂️ &nbsp;{len(problems)} problems tracked<br>
        📋 &nbsp;{len(attempts)} total attempts<br>
        {"📥 &nbsp;<span style='color:#f97316;font-weight:600;'>" + str(pending) + " pending imports</span>" if pending > 0 else "✅ &nbsp;Queue empty"}
    </div>
    """, unsafe_allow_html=True)


# ── Helpers ──────────────────────────────────────────────────────────────────
def bucket_badge(bucket):
    cls = {"Learning":"learning","Practicing":"practicing","Mastered":"mastered"}.get(bucket,"learning")
    return f'<span class="badge badge-{cls}">{bucket}</span>'

def difficulty_badge(difficulty: str) -> str:
    cls = {"Easy": "easy", "Medium": "medium", "Hard": "hard"}.get(difficulty, "medium")
    return f'<span class="badge badge-{cls}">{difficulty}</span>'

def result_color(r):
    return {"solved":"#22c55e","failed":"#f87171","partial":"#fbbf24"}.get(r,"#8b949e")


# ════════════════════════════════════════════════════════════
# DASHBOARD
# ════════════════════════════════════════════════════════════
if page == "🏠  Dashboard":
    st.markdown('<div class="page-header"><h1>Dashboard</h1><p>Your LeetCode practice overview at a glance</p></div>', unsafe_allow_html=True)

    df = pk.get_problems_with_current_bucket()
    bucket_counts = df["bucket"].value_counts().to_dict() if not df.empty else {}
    total, l, p, m = len(df), bucket_counts.get("Learning",0), bucket_counts.get("Practicing",0), bucket_counts.get("Mastered",0)

    c1,c2,c3,c4,c5 = st.columns(5)
    for col,val,lbl,color in [(c1,total,"Total","#58a6ff"),(c2,l,"Learning","#f97316"),(c3,p,"Practicing","#3b82f6"),(c4,m,"Mastered","#22c55e"),(c5,len(attempts),"Attempts","#a78bfa")]:
        col.markdown(f'<div class="metric-card"><div class="value" style="color:{color};">{val}</div><div class="label">{lbl}</div></div>', unsafe_allow_html=True)

    if not df.empty:
        st.markdown('<div class="section-label">All Problems</div>', unsafe_allow_html=True)
        for _, row in df.sort_values("leetcode_number").iterrows():
            last = row["last_attempt_date"] if row["last_attempt_date"] != "1970-01-01" else "Never"
            diff = row.get("difficulty", "Medium") or "Medium"
            st.markdown(f'<div class="problem-row"><span class="num">#{int(row["leetcode_number"])}</span><span class="title">{row["title"]}</span>{difficulty_badge(diff)} &nbsp; {bucket_badge(row["bucket"])}<span style="font-size:0.78rem;color:#484f58;margin-left:1rem;">Last: {last}</span></div>', unsafe_allow_html=True)
    else:
        st.info("No problems tracked yet. Use **Sync from LeetCode** or **Add Problem** to get started!")


# ════════════════════════════════════════════════════════════
# SYNC FROM LEETCODE
# ════════════════════════════════════════════════════════════
elif page == "🔄  Sync from LeetCode":
    st.markdown('<div class="page-header"><h1>Sync from LeetCode</h1><p>Pull your recent accepted submissions automatically</p></div>', unsafe_allow_html=True)

    col_form, col_help = st.columns([3, 2])
    credentials_saved = cfg.config_exists()

    with col_form:
        if credentials_saved:
            # ── Credentials already saved — show compact status ──────────────
            saved = cfg.load_config()
            st.markdown(f"""
            <div class="info-box" style="margin-bottom:1.5rem;">
                <div style="font-size:0.75rem;color:#484f58;text-transform:uppercase;letter-spacing:1px;margin-bottom:0.6rem;">Saved Credentials</div>
                <div style="font-size:0.88rem;color:#e6edf3;">
                    <span style="color:#22c55e;">●</span> &nbsp;
                    Logged in as <strong>{saved['username']}</strong>
                </div>
                <div style="font-size:0.78rem;color:#484f58;margin-top:0.4rem;">
                    Cookies are saved locally and loaded automatically each session.
                </div>
            </div>
            """, unsafe_allow_html=True)

            limit = st.slider("How many recent submissions to check", 5, 20, 10)

            c1, c2 = st.columns([3, 1])
            with c1:
                if st.button("🔄  Sync Now", type="primary", use_container_width=True):
                    with st.spinner("Fetching from LeetCode..."):
                        try:
                            added = sync.queue_new_submissions(
                                saved["username"], saved["session"], saved["csrf"], limit
                            )
                            if added > 0:
                                st.success(f"✅ {added} new submission(s) added to the Import Queue!")
                                st.info("Head to **📥 Import Queue** to review and import them.")
                            else:
                                st.info("No new submissions found. Everything is already tracked or queued.")
                        except Exception as e:
                            st.error(f"Sync failed: {e}\n\nYour cookies may have expired — click 'Update Credentials' to re-enter them.")
            with c2:
                if st.button("Update", use_container_width=True):
                    cfg.clear_config()
                    st.session_state["lc_username"] = ""
                    st.session_state["lc_session"]  = ""
                    st.session_state["lc_csrf"]     = ""
                    st.rerun()

        else:
            # ── No saved credentials — show setup form ───────────────────────
            st.markdown('<div class="section-label">LeetCode Credentials</div>', unsafe_allow_html=True)

            username       = st.text_input("LeetCode Username",        value=st.session_state["lc_username"], placeholder="your_username")
            session_cookie = st.text_input("LEETCODE_SESSION cookie",  value=st.session_state["lc_session"],  type="password", placeholder="eyJ0eXAiOiJKV1Qi...")
            csrf_token     = st.text_input("csrftoken cookie",         value=st.session_state["lc_csrf"],     type="password", placeholder="abc123xyz...")

            if st.button("💾  Save & Sync", type="primary", use_container_width=True):
                if not username or not session_cookie or not csrf_token:
                    st.error("Please fill in all three fields.")
                else:
                    cfg.save_config(username, session_cookie, csrf_token)
                    st.session_state["lc_username"] = username
                    st.session_state["lc_session"]  = session_cookie
                    st.session_state["lc_csrf"]     = csrf_token
                    with st.spinner("Fetching from LeetCode..."):
                        try:
                            added = sync.queue_new_submissions(username, session_cookie, csrf_token, 10)
                            st.success(f"Credentials saved. {added} new submission(s) queued!" if added > 0 else "Credentials saved. No new submissions found.")
                            st.rerun()
                        except Exception as e:
                            cfg.clear_config()
                            st.error(f"Sync failed — credentials not saved: {e}")

    with col_help:
        st.markdown("""
        <div class="info-box" style="margin-top:1.5rem;">
            <div style="font-size:0.75rem;color:#484f58;text-transform:uppercase;letter-spacing:1px;margin-bottom:0.75rem;">
                How to get your cookies
            </div>
            <div style="font-size:0.83rem;color:#8b949e;line-height:1.8;">
                1. Open <strong style="color:#e6edf3;">leetcode.com</strong> and log in<br>
                2. Open DevTools → <strong style="color:#e6edf3;">F12</strong><br>
                3. Go to <strong style="color:#e6edf3;">Application → Cookies</strong><br>
                4. Find <code style="color:#58a6ff;">LEETCODE_SESSION</code> — copy the value<br>
                5. Find <code style="color:#58a6ff;">csrftoken</code> — copy the value<br>
                6. Paste both above
            </div>
            <div style="margin-top:1rem;padding-top:1rem;border-top:1px solid #21262d;font-size:0.78rem;color:#484f58;line-height:1.6;">
                Credentials are saved to <code>.lc_config.json</code> in the project folder.
                Add this file to your <code>.gitignore</code> before pushing to GitHub.
            </div>
        </div>
        <div class="info-box" style="margin-top:1rem;">
            <div style="font-size:0.75rem;color:#484f58;text-transform:uppercase;letter-spacing:1px;margin-bottom:0.75rem;">
                What happens during sync
            </div>
            <div style="font-size:0.83rem;color:#8b949e;line-height:1.8;">
                ✔ Fetches your last N accepted submissions<br>
                ✔ Skips anything already tracked<br>
                ✔ Adds new ones to the Import Queue<br>
                ✔ You review & set bucket/result before importing
            </div>
        </div>
        """, unsafe_allow_html=True)


# ════════════════════════════════════════════════════════════
# IMPORT QUEUE
# ════════════════════════════════════════════════════════════
elif page == "📥  Import Queue":
    st.markdown('<div class="page-header"><h1>Import Queue</h1><p>Review synced submissions and import them into your tracker</p></div>', unsafe_allow_html=True)

    queue = sync.get_pending_queue()

    if not queue:
        st.info("Queue is empty. Run a **Sync** to pull recent submissions, or **Add Problems** manually.")
    else:
        st.markdown(f'<div style="font-size:0.85rem;color:#8b949e;margin-bottom:1rem;">📥 {len(queue)} item(s) waiting to be reviewed</div>', unsafe_allow_html=True)

        for item in queue:
            qid = item["queue_id"]
            with st.container():
                st.markdown(f"""
                <div class="queue-card">
                    <div class="qnum">LeetCode #{item['leetcode_number']}</div>
                    <div class="qtitle">{item['title']}</div>
                    <div class="qmeta">
                        Submitted: {item['submission_date']} &nbsp;·&nbsp;
                        {item['language']} &nbsp;·&nbsp;
                        {item['runtime'] or '—'} &nbsp;·&nbsp;
                        {item.get('difficulty','Medium') or 'Medium'}
                    </div>
                </div>
                """, unsafe_allow_html=True)

                col_b, col_r, col_t, col_n, col_imp, col_skip = st.columns([2, 2, 1.5, 3, 1.5, 1])

                with col_b:
                    bucket = st.selectbox("Bucket", ["Learning","Practicing","Mastered"], key=f"bucket_{qid}")
                with col_r:
                    result = st.selectbox("Result", ["solved","partial","failed"], key=f"result_{qid}")
                with col_t:
                    solve_time = st.number_input("Time (min)", min_value=0, step=1, value=0, key=f"time_{qid}", label_visibility="visible")
                with col_n:
                    notes = st.text_input("Notes", placeholder="optional", key=f"notes_{qid}", label_visibility="visible")
                with col_imp:
                    if st.button("✅ Import", key=f"import_{qid}", type="primary", use_container_width=True):
                        # Add problem if not already tracked
                        existing = db.get_problem_by_number(item["leetcode_number"])
                        if existing:
                            pid = existing["problem_id"]
                        else:
                            pid = db.add_problem(item["leetcode_number"], item["title"], item["link"], item.get("difficulty","Medium") or "Medium")

                        db.log_attempt(
                            pid, bucket, result,
                            attempt_date=item["submission_date"],
                            solve_time=int(solve_time) if solve_time else None,
                            notes=notes.strip() or None,
                        )
                        sync.mark_queue_item(qid, "imported")
                        st.success(f"Imported #{item['leetcode_number']} – {item['title']}")
                        st.rerun()
                with col_skip:
                    if st.button("Skip", key=f"skip_{qid}", use_container_width=True):
                        sync.mark_queue_item(qid, "skipped")
                        st.rerun()

                st.markdown("<hr style='border-color:#21262d;margin:0.5rem 0 1rem 0;'>", unsafe_allow_html=True)


# ════════════════════════════════════════════════════════════
# ADD PROBLEM (manual)
# ════════════════════════════════════════════════════════════
elif page == "➕  Add Problem":
    st.markdown('<div class="page-header"><h1>Add Problem</h1><p>Manually record a LeetCode problem</p></div>', unsafe_allow_html=True)

    col_form, col_help = st.columns([3, 2])
    with col_form:
        lc_num = st.number_input("LeetCode Number", min_value=1, max_value=9999, step=1)
        title  = st.text_input("Problem Title", placeholder="e.g. Sliding Window Maximum")
        auto_link = f"https://leetcode.com/problems/{title.lower().replace(' ','-')}/" if title else ""
        link   = st.text_input("Problem URL", value=auto_link)
        difficulty = st.selectbox("Difficulty", ["Easy", "Medium", "Hard"], index=1)
        st.markdown('<div class="section-label">First Attempt</div>', unsafe_allow_html=True)
        bucket = st.selectbox("Initial Bucket", ["Learning","Practicing","Mastered"])
        result = st.selectbox("Result", ["solved","partial","failed"])
        solve_time = st.number_input("Solve Time (minutes, optional)", min_value=0, step=1, value=0)
        notes  = st.text_area("Notes (optional)")

        if st.button("➕  Add Problem & Log Attempt", type="primary", use_container_width=True):
            if not title.strip():
                st.error("Problem title is required.")
            elif not link.strip():
                st.error("Problem URL is required.")
            elif db.problem_number_exists(int(lc_num)):
                st.error(f"LeetCode #{int(lc_num)} is already tracked.")
            else:
                pid = db.add_problem(int(lc_num), title.strip(), link.strip(), difficulty)
                db.log_attempt(pid, bucket, result, solve_time=int(solve_time) if solve_time else None, notes=notes.strip() or None)
                st.success(f"✅ Added **#{int(lc_num)} – {title}**!")
                st.balloons()

    with col_help:
        st.markdown("""
        <div class="info-box" style="margin-top:1.5rem;">
            <div style="font-size:0.75rem;color:#484f58;text-transform:uppercase;letter-spacing:1px;margin-bottom:1rem;">Bucket Guide</div>
            <div style="margin-bottom:0.8rem;"><span class="badge badge-learning">Learning</span><div style="font-size:0.83rem;color:#8b949e;margin-top:0.3rem;">New or failed. Still building intuition.</div></div>
            <div style="margin-bottom:0.8rem;"><span class="badge badge-practicing">Practicing</span><div style="font-size:0.83rem;color:#8b949e;margin-top:0.3rem;">Solved once confidently. Reinforcing the pattern.</div></div>
            <div><span class="badge badge-mastered">Mastered</span><div style="font-size:0.83rem;color:#8b949e;margin-top:0.3rem;">Consistently solved. Keep revisiting to maintain.</div></div>
        </div>
        """, unsafe_allow_html=True)


# ════════════════════════════════════════════════════════════
# PICK PROBLEM
# ════════════════════════════════════════════════════════════
elif page == "🎯  Pick Problem":
    st.markdown('<div class="page-header"><h1>Pick a Problem</h1><p>Smart picker scores every problem across difficulty, recency, results and history</p></div>', unsafe_allow_html=True)

    # ── DEBUG panel ──────────────────────────────────────────────────────────
    # with st.expander("🐛 Debug — scores & session state"):
    #     import pandas as pd
    #     scores_df = pk.compute_scores()
    #     st.write("**Session state picked:**", st.session_state.get("picked"))
    #     st.write("**Session state picked_mode:**", st.session_state.get("picked_mode"))
    #     if scores_df.empty:
    #         st.warning("compute_scores() returned empty — no problems in DB?")
    #     else:
    #         display = scores_df[["leetcode_number","title","difficulty","bucket","score","mode","last_result","failure_rate","days_since"]].copy()
    #         display["score"] = display["score"].round(3)
    #         display["failure_rate"] = display["failure_rate"].round(2)
    #         st.dataframe(display, use_container_width=True, hide_index=True)

    MODE_META = {
        "challenge": {
            "label":    "🔥  Challenge Mode",
            "desc":     "High-scoring problems — hard, frequently failed, or long untouched.",
            "key":      "challenge",
            "color":    "#f87171",
        },
        "grind": {
            "label":    "💪  Steady Grind",
            "desc":     "Mid-range problems — a balanced mix to keep you sharp.",
            "key":      "grind",
            "color":    "#60a5fa",
        },
        "chill": {
            "label":    "😌  Chill Mode",
            "desc":     "Low-pressure problems — easier, well-practiced, recently solved.",
            "key":      "chill",
            "color":    "#86efac",
        },
    }

    col_pick, col_info = st.columns([3, 2])
    with col_pick:
        mode_choice = st.radio(
            "Mode",
            list(MODE_META.keys()),
            format_func=lambda m: MODE_META[m]["label"],
            label_visibility="collapsed",
        )
        st.markdown(
            f'<div style="font-size:0.85rem;color:#8b949e;margin-bottom:1rem;">{MODE_META[mode_choice]["desc"]}</div>',
            unsafe_allow_html=True,
        )

        if st.button("🎲  Pick a Problem", type="primary", use_container_width=True):
            last_id = st.session_state.get("picked")
            last_id = last_id.get("problem_id") if isinstance(last_id, dict) and last_id else None
            st.session_state["picked"]      = pk.pick_problem(mode_choice, exclude_id=last_id)
            st.session_state["picked_mode"] = mode_choice

    with col_info:
        st.image("https://leetcode.com/static/images/LeetCode_logo.png", width=150)

    if "picked" in st.session_state:
        p = st.session_state["picked"]
        if p is None:
            st.warning("No problems available for this mode yet. Add more problems or log more attempts.")
        else:
            days      = int(p.get("days_since", 0))
            last_raw  = p.get("last_attempt_date", "1970-01-01")
            last_str  = "Never practiced" if last_raw == "1970-01-01" else f"Last: {last_raw}"
            diff      = p.get("difficulty", "Medium") or "Medium"
            mode_color = MODE_META.get(st.session_state.get("picked_mode","grind"), {}).get("color","#8b949e")

            st.markdown(f"""
            <div class="pick-card">
                <div class="problem-num">LeetCode #{int(p['leetcode_number'])}</div>
                <div class="problem-title">{p['title']}</div>
                <div class="meta">
                    {difficulty_badge(diff)} &nbsp;
                    {bucket_badge(p['bucket'])} &nbsp;
                    {last_str} &nbsp;
                    <span style="color:#484f58;">• {days}d ago</span>
                </div>
            </div>
            """, unsafe_allow_html=True)
            st.link_button("🔗  Open on LeetCode", p["link"], use_container_width=True)

    # with col_info:
    #     st.markdown("""
    #     <div class="info-box" style="margin-top:3rem;">
    #         <div style="font-size:0.75rem;color:#484f58;text-transform:uppercase;letter-spacing:1px;margin-bottom:0.75rem;">How Scoring Works</div>
    #         <div style="font-size:0.82rem;color:#8b949e;line-height:1.9;">
    #             Every problem gets a global score based on multiple factors like last solved date, difficulty level etc.<br>
    #             <!-- <span style="color:#e6edf3;">30%</span> Last result<br>
    #              <span style="color:#e6edf3;">25%</span> Historical fail rate<br>
    #              <span style="color:#e6edf3;">20%</span> Difficulty<br>
    #              <span style="color:#e6edf3;">15%</span> Recency<br>
    #              <span style="color:#e6edf3;">10%</span> Avg solve time -->
    #         </div>
    #         <div style="margin-top:1rem;padding-top:1rem;border-top:1px solid #21262d;font-size:0.78rem;color:#484f58;line-height:1.8;">
    #             <span style="color:#f87171;">●</span> Challenge  — score ≥ 0.67<br>
    #             <span style="color:#60a5fa;">●</span> Steady Grind — 0.33–0.67<br>
    #             <span style="color:#86efac;">●</span> Chill Mode  — score &lt; 0.33
    #         </div>
    #     </div>
    #     """, unsafe_allow_html=True)


# ════════════════════════════════════════════════════════════
# LOG ATTEMPT
# ════════════════════════════════════════════════════════════
elif page == "📝  Log Attempt":
    st.markdown('<div class="page-header"><h1>Log Attempt</h1><p>Record a new attempt for a tracked problem</p></div>', unsafe_allow_html=True)

    problems = db.get_all_problems()
    if not problems:
        st.info("No problems tracked yet.")
    else:
        col_form, col_hist = st.columns([2, 3])
        with col_form:
            options = {f"#{p['leetcode_number']} — {p['title']}": p['problem_id'] for p in problems}
            selected_label = st.selectbox("Select Problem", list(options.keys()))
            selected_id = options[selected_label]
            bucket = st.selectbox("Bucket", ["Learning","Practicing","Mastered"])
            result = st.selectbox("Result", ["solved","partial","failed"])
            solve_time = st.number_input("Solve Time (min, optional)", min_value=0, step=1, value=0)
            attempt_date = st.date_input("Attempt Date", value=date.today())
            notes = st.text_area("Notes (optional)")

            if st.button("📝  Log Attempt", type="primary", use_container_width=True):
                db.log_attempt(selected_id, bucket, result,
                    attempt_date=attempt_date.isoformat(),
                    solve_time=int(solve_time) if solve_time else None,
                    notes=notes.strip() or None)
                st.success("✅ Attempt logged!")

        with col_hist:
            st.markdown('<div class="section-label">Attempt History</div>', unsafe_allow_html=True)
            hist = db.get_attempts_for_problem(selected_id)
            for a in hist:
                rc = result_color(a["result"])
                st.markdown(f"""
                <div class="attempt-row">
                    <span style="color:#e6edf3;font-weight:500;">{a['attempt_date']}</span> &nbsp;·&nbsp;
                    {bucket_badge(a['bucket'])} &nbsp;·&nbsp;
                    <span style="color:{rc};font-weight:600;">{a['result']}</span>
                    {f" &nbsp;·&nbsp; {a['solve_time']}m" if a['solve_time'] else ""}
                    {f"<br><span style='color:#6e7681;font-size:0.8rem;'>{a['notes']}</span>" if a['notes'] else ""}
                </div>
                """, unsafe_allow_html=True)
