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
#         if st.button("Logout"):
#             st.session_state["authentication_status"] = None
#             st.session_state["username"] = None
#             st.session_state["name"] = None
#             st.rerun()


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

        with st.expander("🛠 Admin: Set Game Winners"):
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
        col1, space, col2 = st.columns([3, .5, 1.5])
        with col1:
            st.title("Make Picks")
        with col2:
            # Select tournament
            cursor.execute("SELECT tournament_id, name, start_time FROM tournaments ORDER BY start_time")
            tournaments = cursor.fetchall()
            if not tournaments:
                st.warning("No tournaments available")
            else:
                tournament_map = {t["name"]: t["tournament_id"] for t in tournaments}
                selected_name = st.selectbox("Tournament", list(tournament_map.keys()))
                tournament_id = tournament_map[selected_name]

        st.sidebar.divider()

        # Current time (UTC)
        from datetime import timezone
        now = datetime.now(timezone.utc)

        # Get tournament start time to lock picks
        cursor.execute("SELECT start_time FROM tournaments WHERE tournament_id=%s", (tournament_id,))
        tournament_info = cursor.fetchone()
        start_time = tournament_info["start_time"] if tournament_info else None
        locked = start_time and now >= start_time

        st.write("")

        # For each tier (1–5)
        for tier_number in range(1, 6):
            st.subheader(f"Tier {tier_number}")

            # Get players for this tier
            cursor.execute("""
                SELECT p.player_id, p.name
                FROM tiers t
                JOIN players p ON p.player_id = t.player_id
                WHERE t.tournament_id=%s AND t.tier_number=%s
            """, (tournament_id, tier_number))
            players = cursor.fetchall()
            if not players:
                st.info("No players assigned to this tier")
                continue

            # Get existing pick for this user/tier
            cursor.execute("""
                SELECT player_id FROM picks
                WHERE username=%s AND tournament_id=%s AND tier_number=%s
            """, (username, tournament_id, tier_number))
            existing = cursor.fetchone()
            existing_pick = existing["player_id"] if existing else None

            # Options
            player_options = {p["name"]: p["player_id"] for p in players}

            if not locked:
                choice_name = None
                # If existing pick exists, get name
                for name, pid in player_options.items():
                    if pid == existing_pick:
                        choice_name = name

                choice_name = st.selectbox(
                    "Select Player",
                    [""] + list(player_options.keys()),
                    index=(list(player_options.keys()).index(choice_name)+1 if choice_name else 0),
                    key=f"pick_{tournament_id}_tier{tier_number}_{safe_key(username)}"
                )

                if st.button("Save", key=f"save_{tournament_id}_tier{tier_number}_{safe_key(username)}"):
                    # Delete old pick
                    cursor.execute("""
                        DELETE FROM picks
                        WHERE username=%s AND tournament_id=%s AND tier_number=%s
                    """, (username, tournament_id, tier_number))
                    # Insert new pick
                    cursor.execute("""
                        INSERT INTO picks (username, tournament_id, tier_number, player_id, timestamp)
                        VALUES (%s, %s, %s, %s, %s)
                    """, (username, tournament_id, tier_number, player_options.get(choice_name), now.isoformat()))
                    conn.commit()
                    st.success(f"Saved pick: {choice_name}")
                    st.rerun()
            else:
                if existing_pick:
                    # Display name for locked pick
                    locked_name = next((name for name, pid in player_options.items() if pid == existing_pick), "Unknown")
                    st.info(f"Your locked pick: **{locked_name}**")
                else:
                    st.warning("No pick submitted")


    elif page == "All Picks":
        col1, space, col2 = st.columns([3, .5, 1.5])
        with col1:
            st.title("All Picks")
        with col2:
            # Select tournament
            cursor.execute("SELECT tournament_id, name, start_time FROM tournaments ORDER BY start_time")
            tournaments = cursor.fetchall()
            if not tournaments:
                st.warning("No tournaments available")
            else:
                tournament_map = {t["name"]: t["tournament_id"] for t in tournaments}
                selected_name = st.selectbox("Tournament", list(tournament_map.keys()))
                tournament_id = tournament_map[selected_name]

        st.sidebar.divider()
        st.write("")

        # Get current time
        from datetime import datetime, timezone
        now = datetime.now(timezone.utc)

        # Get tournament start time
        cursor.execute("SELECT start_time FROM tournaments WHERE tournament_id=%s", (tournament_id,))
        tournament_info = cursor.fetchone()
        start_time = tournament_info["start_time"] if tournament_info else None
        now = datetime.now(timezone.utc)
        locked = start_time and now < start_time  # locked = True if tournament hasn't started

        # 1️⃣ Get all users
        cursor.execute("SELECT username, name FROM users")
        users = cursor.fetchall()
        usernames = [u["username"] for u in users]
        name_map = {u["username"]: u["name"] for u in users}

        # 2️⃣ Get picks for this tournament
        cursor.execute("""
            SELECT username, tier_number, player_id
            FROM picks
            WHERE tournament_id=%s
        """, (tournament_id,))
        rows = cursor.fetchall()

        # 3️⃣ Build lookup: username -> tier_number -> player_id
        pick_map = {u: {tier: None for tier in range(1, 6)} for u in usernames}
        for row in rows:
            pick_map[row["username"]][row["tier_number"]] = row["player_id"]

        # 4️⃣ Build display table
        table = []
        # When building table
        for user in users:
            username = user["username"]
            row_data = {"User": user["name"]}

            for tier_number in range(1, 6):
                pick_id = pick_map[username][tier_number]

                if pick_id and not locked:
                    # Show pick if tournament started
                    cursor.execute("SELECT name FROM players WHERE player_id=%s", (pick_id,))
                    player = cursor.fetchone()
                    pick_name = player["name"] if player else "Unknown"
                    row_data[f"Tier {tier_number}"] = pick_name
                else:
                    # Tournament not started or pick not made
                    row_data[f"Tier {tier_number}"] = "🔒"

            table.append(row_data)

        # 5️⃣ Display as DataFrame
        import pandas as pd
        df = pd.DataFrame(table)

        column_config = {"User": st.column_config.TextColumn("User", width="small")}
        for tier_number in range(1, 6):
            column_config[f"Tier {tier_number}"] = st.column_config.TextColumn(f"Tier {tier_number}", width="medium")

        st.dataframe(
            df,
            width="stretch",
            hide_index=True,
            column_config=column_config,
            row_height=50
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