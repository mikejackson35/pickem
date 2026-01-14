import streamlit as st
from datetime import datetime
import psycopg2
from psycopg2.extras import RealDictCursor
import bcrypt

from datetime import datetime, timezone
from utils import TEAM_ABBR, TEAM_ALIAS

import os
import re


# ----------------------------
# Database Connection
# ----------------------------
def get_connection():
    try:
        conn = psycopg2.connect(
            st.secrets["SUPABASE_DB_URL"],  # must be your full Supabase URI
            sslmode="require",
            cursor_factory=RealDictCursor
        )
        return conn
    except Exception as e:
        st.error(f"Failed to connect to Supabase: {e}")
        return None

# Try to connect
conn = get_connection()
if conn is None:
    st.stop()  # Stop the app if DB connection fails
cursor = conn.cursor()


# ----------------------------
# ADMINS
# ----------------------------
ADMINS = {"mj"}  # set of usernames allowed to see admin tools

# ----------------------------
# ROUND ORDER
# ----------------------------
ROUND_ORDER = [
    "Wild Card",
    "Divisional",
    "Conference",
    "Superbowl"
]


# ----------------------------
# HELPER FUNCTIONS
# ----------------------------
def safe_key(s: str) -> str:
    """Convert string to Streamlit-safe widget key"""
    s = s.replace(" ", "_").replace("@", "at")
    return re.sub(r"[^0-9a-zA-Z_]", "", s)

def add_test_user():
    cursor.execute("SELECT 1 FROM users WHERE username = %s", ("mj",))
    if cursor.fetchone() is None:
        password = "password123"
        password_hash = bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()
        cursor.execute(
            "INSERT INTO users (username, name, password_hash) VALUES (%s, %s, %s)",
            ("mj", "Mike", password_hash)
        )
        conn.commit()

add_test_user()

# ----------------------------
# AUTHENTICATION (Manual with bcrypt)
# ----------------------------

if "authentication_status" not in st.session_state:
    st.session_state["authentication_status"] = None
    st.session_state["username"] = None
    st.session_state["name"] = None

auth_status = st.session_state["authentication_status"]
username = st.session_state["username"]
name = st.session_state["name"]

# Manual Login Form
if auth_status is not True:
    st.title("Login")
    
    with st.form("login_form"):
        login_username = st.text_input("Username")
        # login_username = login_username.strip().lower()
        login_password = st.text_input("Password", type="password")
        submit = st.form_submit_button("Login")
        
        if submit:
            if login_username and login_password:
                cursor.execute(
                    "SELECT username, name, password_hash FROM users WHERE username=%s",
                    (login_username,)
                )
                user = cursor.fetchone()
                
                if user and bcrypt.checkpw(login_password.encode(), user["password_hash"].encode()):
                    st.session_state["authentication_status"] = True
                    st.session_state["username"] = user["username"]
                    st.session_state["name"] = user["name"]
                    st.success("Login successful!")
                    st.rerun()
                else:
                    st.session_state["authentication_status"] = False
                    st.error("Username/password is incorrect")
            else:
                st.error("Please enter both username and password")

# ----------------------------
# SIGN UP (ONLY SHOWN WHEN NOT LOGGED IN)
# ----------------------------
if not auth_status:
    with st.expander("Create a New Account"):
        new_username = st.text_input("Username")
        # new_username = new_username.strip().lower()
        new_name = st.text_input("Name")
        new_pw = st.text_input("Password", type="password")

        if st.button("Create Account"):
            if not all([new_username, new_name, new_pw]):
                st.error("All fields are required")
            else:
                cursor.execute(
                    "SELECT 1 FROM users WHERE username=%s",
                    (new_username,)
                )
                if cursor.fetchone():
                    st.error("Username already exists")
                else:
                    pw_hash = bcrypt.hashpw(
                        new_pw.encode(), bcrypt.gensalt()
                    ).decode()

                    cursor.execute("""
                        INSERT INTO users (username, name, password_hash)
                        VALUES (%s, %s, %s)
                    """, (new_username, new_name, pw_hash))
                    conn.commit()

                    st.success("Account created! Please log in above.")
                    st.rerun()

# ----------------------------
# LOGOUT
# ----------------------------
if auth_status:
    with st.sidebar:
        st.success(f"Logged in as {name}")

# ----------------------------
# APP
# ----------------------------
if auth_status:

    # PASSWORD CHANGE
    with st.sidebar.expander("Change Password"):
        old_pw = st.text_input("Old Password", type="password", key="old_pw")
        new_pw = st.text_input("New Password", type="password", key="new_pw")
        confirm_pw = st.text_input("Confirm New Password", type="password", key="confirm_pw")
        if st.button("Update Password"):
            if not all([old_pw, new_pw, confirm_pw]):
                st.error("All fields are required")
            else:
                cursor.execute("SELECT password_hash FROM users WHERE username=%s", (username,))
                result = cursor.fetchone()
                if result:
                    stored_hash = result["password_hash"]
                    if bcrypt.checkpw(old_pw.encode(), stored_hash.encode()):
                        if new_pw == confirm_pw:
                            new_hash = bcrypt.hashpw(new_pw.encode(), bcrypt.gensalt()).decode()
                            cursor.execute("UPDATE users SET password_hash=%s WHERE username=%s", (new_hash, username))
                            conn.commit()
                            st.success("Password updated successfully!")
                            st.rerun()
                        else:
                            st.error("New passwords do not match")
                    else:
                        st.error("Old password incorrect")
                else:
                    st.error("User not found")

    # st.sidebar.divider()

    # ----------------------------
    # ADMIN TOOLS
    # ----------------------------
    if username in ADMINS:

        with st.sidebar.expander("🛠 Admin: Set Game Winners"):
            cursor.execute("SELECT game_id, week, home, away, winner FROM games")
            games = cursor.fetchall()

            if not games:
                st.info("No games found in database")
            else:
                # Sort games by round order
                games_sorted = sorted(games, key=lambda g: ROUND_ORDER.index(g["week"]))
                
                for idx, game in enumerate(games_sorted):
                    game_id = game["game_id"]
                    week = game["week"]
                    home = game["home"]
                    away = game["away"]
                    winner = game["winner"]
                    
                    # Show round header
                    if idx == 0 or games_sorted[idx-1]["week"] != week:
                        st.subheader(week)
                    
                    col1, col2 = st.columns([3, 1])
                    
                    with col1:
                        # Strip whitespace and handle None
                        winner_clean = winner.strip() if winner else None
                        home_clean = home.strip()
                        away_clean = away.strip()
                        
                        # Safely determine index
                        options = ["", home_clean, away_clean]
                        try:
                            current_index = options.index(winner_clean) if winner_clean else 0
                        except ValueError:
                            current_index = 0
                        
                        choice = st.selectbox(
                            f"{away_clean} @ {home_clean}",
                            options,
                            index=current_index,
                            key=f"winner_{idx}"
                        )

                    with col2:
                        st.space(size='small')
                        if st.button("Save", key=f"save_{idx}"):
                            cursor.execute(
                                "UPDATE games SET winner=%s WHERE game_id=%s",
                                (choice if choice else None, game_id)
                            )
                            conn.commit()
                            st.success("Saved!")
                            st.rerun()

    st.sidebar.divider()

    # PAGE NAVIGATION
    PAGES = ["Leaderboard", "All Picks", "Make Picks"]
    page = st.sidebar.radio("Go to", PAGES)


    if page == "Make Picks":
            
            col1, col2 = st.columns([4,1])
            with col1:
                st.title("📝 Make Your Picks")
            with col2:

                # Get available rounds from database
                cursor.execute("SELECT DISTINCT week FROM games ORDER BY week")
                available_weeks = [row["week"] for row in cursor.fetchall()]

                # Filter ROUND_ORDER to only show rounds that exist in DB
                week = st.selectbox(
                    "Select Round",
                    [r for r in ROUND_ORDER if r in available_weeks]
                )

            # Fix deprecated datetime
            from datetime import timezone
            now = datetime.now(timezone.utc)
            
            # Get games from database for selected round
            cursor.execute("SELECT game_id, week, home, away, kickoff FROM games WHERE week=%s ORDER BY kickoff", (week,))
            week_games = cursor.fetchall()

            st.write('')

            for game in week_games:
                locked = now >= game["kickoff"]
                matchup = f'{game["away"]} @ {game["home"]}'
                st.subheader(matchup)
                kickoff_str = game["kickoff"].strftime("%A %I:%M %p").lstrip("0")
                st.caption(f"{kickoff_str} EST")

                # Get existing pick - fix dictionary access
                cursor.execute("SELECT pick FROM picks WHERE username=%s AND game_id=%s", (username, game["game_id"]))
                existing = cursor.fetchone()
                existing_pick = existing["pick"] if existing else None

                if not locked:
                    choice = st.radio(
                        "Pick winner",
                        [game["away"], game["home"]],
                        index=(0 if existing_pick == game["away"] else 1 if existing_pick == game["home"] else 0),
                        key=f"pick_{safe_key(game['game_id'])}_{safe_key(username)}"
                    )
                    
                    if st.button("Save Pick", key=f"save_{safe_key(username)}_{safe_key(game['game_id'])}"):
                        # Delete old pick first, then insert new one
                        cursor.execute(
                            "DELETE FROM picks WHERE username=%s AND game_id=%s", 
                            (username, game["game_id"])
                        )
                        cursor.execute(
                            "INSERT INTO picks (username, game_id, pick, timestamp) VALUES (%s, %s, %s, %s)",
                            (username, game["game_id"], choice, now.isoformat())
                        )
                        conn.commit()
                        st.success(f"Saved pick: {choice}")
                        st.rerun()

                else:
                    if existing_pick:
                        st.info(f"Your pick: **{existing_pick}**")
                    else:
                        st.warning("No pick submitted")


    elif page == "All Picks":
            st.title("📊 All Picks")
            st.sidebar.divider()

            # Get available rounds from database
            cursor.execute("SELECT DISTINCT week FROM games")
            available_weeks = [row["week"] for row in cursor.fetchall()]

            # Filter ROUND_ORDER to only show rounds that exist in DB
            week = st.sidebar.selectbox(
                "Select Round",
                [r for r in ROUND_ORDER if r in available_weeks]
            )

            # Get games from database for selected round
            cursor.execute("SELECT game_id, week, home, away, kickoff FROM games WHERE week=%s", (week,))
            week_games = cursor.fetchall()
            game_ids = [g["game_id"] for g in week_games]

            if not game_ids:
                st.info("No games for this round.")
            else:
                # 1️⃣ Get all users and their full names
                cursor.execute("SELECT username, name FROM users")
                users = cursor.fetchall()  # list of dicts
                usernames = [u["username"] for u in users]
                name_map = {u["username"]: u["name"] for u in users}

                # 2️⃣ Get picks for these games
                placeholders = ",".join(["%s"] * len(game_ids))
                cursor.execute(
                    f"""
                    SELECT username, game_id, pick
                    FROM picks
                    WHERE game_id IN ({placeholders})
                    """,
                    tuple(game_ids)
                )
                rows = cursor.fetchall()

                # 3️⃣ Build lookup: username -> game_id -> pick
                pick_map = {u: {gid: None for gid in game_ids} for u in usernames}
                for row in rows:
                    pick_map[row["username"]][row["game_id"]] = row["pick"]

                # 4️⃣ Build display table with lock logic
                from datetime import timezone
                now = datetime.now(timezone.utc)
                table = []
                for user in users:
                    username = user["username"]
                    full_name = user["name"]
                    row_data = {"User": full_name}

                    for g in week_games:
                        locked = now >= g["kickoff"]

                        if locked:
                            pick = pick_map[username][g["game_id"]]
                            row_data[g["game_id"]] = pick if pick else "—"
                        else:
                            row_data[g["game_id"]] = "🔒"

                    table.append(row_data)

                # 5️⃣ Display as DataFrame
                import pandas as pd
                df = pd.DataFrame(table)

                st.dataframe(
                    df,
                    width="stretch",
                    hide_index=True
                )

    elif page == "Leaderboard":
        st.title("🏆 Leaderboard")
        st.sidebar.divider()

        # 1️⃣ Get all users (username + full name)
        cursor.execute("SELECT username, name FROM users ORDER BY name")
        users = cursor.fetchall()  # list of dicts

        # Mapping for easy lookup
        name_map = {user["username"]: user["name"] for user in users}
        usernames = [user["username"] for user in users]

        # 2️⃣ Initialize points to 0 for all users
        user_points = {u: 0 for u in usernames}

        # 3️⃣ Define round weights
        ROUND_WEIGHTS = {
            "Wild Card": 1,
            "Divisional": 2,
            "Conference": 3,
            "Superbowl": 4
        }

        # 4️⃣ Get all picks
        cursor.execute("SELECT username, game_id, pick FROM picks")
        all_picks = cursor.fetchall()

        for pick_row in all_picks:
            username = pick_row["username"]
            game_id = pick_row["game_id"]
            pick = pick_row["pick"]
            
            cursor.execute("SELECT winner, week FROM games WHERE game_id=%s", (game_id,))
            result = cursor.fetchone()
            if result:
                winner = result["winner"]
                week = result["week"]
                if winner and pick == winner:
                    user_points[username] += ROUND_WEIGHTS.get(week, 1)

        # 5️⃣ Build DataFrame with full names
        import pandas as pd

        df = pd.DataFrame({
            "User": [name_map.get(u, u) for u in usernames],
            "Points": [user_points[u] for u in usernames]
        })

        # 6️⃣ Sort by points descending
        df = df.sort_values("Points", ascending=False).reset_index(drop=True)

        # 7️⃣ Display in Streamlit
        st.dataframe(
            df,
            width="stretch",
            hide_index=True
        )


# ----------------------------
# LOGOUT
# ----------------------------
if auth_status is True:
    with st.sidebar:
        # st.success(f"Logged in as {name}")
        if st.button("Logout"):
            st.session_state["authentication_status"] = None
            st.session_state["username"] = None
            st.session_state["name"] = None
            st.rerun()