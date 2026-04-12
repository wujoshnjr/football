import streamlit as st
import requests
import numpy as np
import pandas as pd
import sqlite3
from datetime import datetime, timedelta, timezone

st.set_page_config(page_title="Hedge Fund v33 Data Warehouse", layout="wide")

# =========================
# 📡 CORE APIS (LOCKED)
# =========================
ODDS_API_KEY = "1ecd27d55ae4f667d16b08d41c00728f"
SPORTMONKS_KEY = "Rd1ZOCcgubiZpmMDSrf2y4DffiiuzFqyrAqRpqqR0AnVCoK2K29iGWQVm9Lm"
NEWS_API_KEY = "aca30b5c29cb379c1d38cc4be8514a64df8d124831e2f07f55714cc2a02ce176"

# =========================
# 🗄️ DATA WAREHOUSE
# =========================
conn = sqlite3.connect("hf_v33.db", check_same_thread=False)
c = conn.cursor()

c.execute("""
CREATE TABLE IF NOT EXISTS matches (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    match TEXT,
    time TEXT,
    pick TEXT,
    odds REAL,
    prob REAL,
    ev REAL
)
""")

c.execute("""
CREATE TABLE IF NOT EXISTS simulations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    match TEXT,
    win_rate REAL,
    avg_return REAL,
    volatility REAL
)
""")

conn.commit()

# =========================
# 🕒 TIME SYSTEM
# =========================
def to_taipei(utc_str):
    try:
        dt = datetime.fromisoformat(utc_str.replace("Z", "+00:00"))
        return dt + timedelta(hours=8)
    except:
        return None

def within_24h(dt):
    now = datetime.now(timezone.utc)
    return 0 <= (dt - now).total_seconds() <= 86400

# =========================
# 📡 DATA FETCH
# =========================
def get_matches():
    url = "https://api.the-odds-api.com/v4/sports/soccer_epl/odds/"
    params = {
        "apiKey": ODDS_API_KEY,
        "regions": "uk",
        "markets": "h2h",
        "oddsFormat": "decimal"
    }
    try:
        r = requests.get(url, timeout=10)
        data = r.json()
        return data if isinstance(data, list) else []
    except:
        return []

# =========================
# 🧠 MODEL ENGINE
# =========================
def strength(team):
    return 0.3 + (abs(hash(team)) % 1000) / 2000

def xg(team):
    return 1.0 + (abs(hash(team + "xg")) % 100) / 100

def ev(p, odds):
    return p * odds - 1

def kelly(p, odds):
    b = odds - 1
    return max(0, (b*p - (1-p)) / b)

# =========================
# 🧪 20,000 SIMULATION ENGINE (NEW)
# =========================
def monte_carlo_20000(p, odds):

    results = []

    for _ in range(20000):

        win = np.random.rand() < p

        if win:
            results.append(odds - 1)
        else:
            results.append(-1)

    results = np.array(results)

    return {
        "win_rate": np.mean(results > 0),
        "avg_return": np.mean(results),
        "volatility": np.std(results)
    }

# =========================
# 🖥 UI
# =========================
st.title("🏦 v33 Hedge Fund Data Warehouse + 20K Simulation")

if st.button("🚀 RUN DATA WAREHOUSE ENGINE"):

    matches = get_matches()
    results = []

    for m in matches:

        try:
            home = m["home_team"]
            away = m["away_team"]

            # =========================
            # 🕒 24H FILTER
            # =========================
            dt = datetime.fromisoformat(m["commence_time"].replace("Z", "+00:00"))
            if not within_24h(dt):
                continue

            taipei_time = to_taipei(m["commence_time"])
            taipei_str = taipei_time.strftime("%Y-%m-%d %H:%M")

            odds = {}

            for b in m["bookmakers"]:
                for mk in b["markets"]:
                    if mk["key"] == "h2h":
                        for o in mk["outcomes"]:
                            odds[o["name"]] = o["price"]

            if home not in odds or away not in odds:
                continue

            # =========================
            # MODEL
            # =========================
            sh = strength(home)
            sa = strength(away)

            xh = xg(home)
            xa = xg(away)

            p_home = (sh + xh) / (sh + sa + xh + xa)

            if ev(p_home, odds[home]) > ev(1 - p_home, odds[away]):
                pick = home
                p = p_home
                entry = odds[home]
            else:
                pick = away
                p = 1 - p_home
                entry = odds[away]

            ev_v = ev(p, entry)
            k = kelly(p, entry)

            # =========================
            # 🧪 20K SIMULATION
            # =========================
            sim = monte_carlo_20000(p, entry)

            # =========================
            # STORE MATCH
            # =========================
            c.execute("""
                INSERT INTO matches (match, time, pick, odds, prob, ev)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (
                f"{home} vs {away}",
                taipei_str,
                pick,
                entry,
                p,
                ev_v
            ))

            # =========================
            # STORE SIMULATION
            # =========================
            c.execute("""
                INSERT INTO simulations (match, win_rate, avg_return, volatility)
                VALUES (?, ?, ?, ?)
            """, (
                f"{home} vs {away}",
                sim["win_rate"],
                sim["avg_return"],
                sim["volatility"]
            ))

            conn.commit()

            results.append({
                "Match": f"{home} vs {away}",
                "Time (Taipei)": taipei_str,
                "Pick": pick,
                "Odds": entry,
                "Prob": round(p, 3),
                "EV": round(ev_v, 3),
                "Kelly": round(k, 3),
                "Sim Win Rate (20k)": round(sim["win_rate"], 3),
                "Sim Avg Return": round(sim["avg_return"], 3),
                "Sim Volatility": round(sim["volatility"], 3)
            })

        except:
            continue

    df = pd.DataFrame(results)

    if df.empty:
        st.warning("⚠️ No data in 24h window")
        st.stop()

    df = df.sort_values("EV", ascending=False)

    st.success(f"💰 Matches: {len(df)} | Simulation runs: 20,000 per match")

    st.dataframe(df, use_container_width=True)

    st.subheader("📊 System Summary")

    st.write({
        "Avg EV": df["EV"].mean(),
        "Avg Win Rate (Sim)": df["Sim Win Rate (20k)"].mean(),
        "Avg Volatility": df["Sim Volatility"].mean()
    })
