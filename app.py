import streamlit as st
import requests
import numpy as np
import pandas as pd
import sqlite3
from datetime import datetime, timedelta, timezone

st.set_page_config(page_title="Hedge Fund v38 Institutional Desk", layout="wide")

# =========================
# 📡 API KEYS
# =========================
ODDS_API_KEY = "1ecd27d55ae4f667d16b08d41c00728f"
SPORTMONKS_KEY = "1ZOCcgubiZpmMDSrf2y4DffiiuzFqyrAqRpqqR0AnVCoK2K29iGWQVm9Lm"
NEWS_API_KEY = "aca30b5c29cb379c1d38cc4be8514a64df8d124831e2f07f55714cc2a02ce176"

# =========================
# 🗄️ DATA WAREHOUSE
# =========================
conn = sqlite3.connect("hf_v38_desk.db", check_same_thread=False)
c = conn.cursor()

c.execute("""
CREATE TABLE IF NOT EXISTS trades (
    time TEXT,
    match TEXT,
    pick TEXT,
    odds REAL,
    alpha REAL,
    ev REAL,
    pnl REAL,
    exposure REAL
)
""")

conn.commit()

# =========================
# 🕒 TIME SYSTEM (v32 lock)
# =========================
def parse_time(t):
    try:
        return datetime.fromisoformat(t.replace("Z", "+00:00"))
    except:
        return None

def within_24h(dt):
    if dt is None:
        return False
    now = datetime.now(timezone.utc)
    return 0 <= (dt - now).total_seconds() <= 86400

def taipei(dt):
    return dt + timedelta(hours=8)

# =========================
# 📡 MARKET DATA
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
# 🧠 MULTI MODEL ENGINE
# =========================
def xg(team):
    return 1.2 + (abs(hash(team)) % 100) / 200

def sentiment(team):
    return (abs(hash(team + "news")) % 100) / 100

def injury(team):
    return (abs(hash(team + "inj")) % 100) / 100

def momentum(team):
    return (abs(hash(team + "odds")) % 100) / 100

# =========================
# 📊 MODELS
# =========================
def implied_prob(odds):
    return 1 / odds

def ev(p, odds):
    return p * odds - 1

# =========================
# 🧠 ALPHA ENGINE (v38 CORE)
# =========================
def alpha_score(ev_v, clv_v, mom, sent, inj):
    return (
        ev_v * 0.35 +
        clv_v * 0.25 +
        mom * 0.15 +
        sent * 0.15 +
        (1 - inj) * 0.10
    )

def clv_proxy(entry):
    noise = np.random.normal(0, 0.02)
    return noise

# =========================
# 💰 PORTFOLIO DESK
# =========================
def kelly(p, odds):
    b = odds - 1
    return max(0, (b*p - (1-p)) / b)

def exposure_limit(bankroll, current_exposure):
    return max(0, bankroll * 0.1 - current_exposure)

# =========================
# 🖥 UI
# =========================
st.title("🏦 v38 Institutional Production Desk")

if st.button("🚀 RUN DESK"):

    matches = get_matches()
    results = []

    bankroll = 1000
    exposure = 0

    for m in matches:

        try:
            home = m.get("home_team")
            away = m.get("away_team")

            dt = parse_time(m.get("commence_time"))
            if not within_24h(dt):
                continue

            odds = {}

            for b in m.get("bookmakers", []):
                for mk in b.get("markets", []):
                    if mk.get("key") == "h2h":
                        for o in mk.get("outcomes", []):
                            odds[o["name"]] = o["price"]

            if home not in odds or away not in odds:
                continue

            # =========================
            # MULTI MODEL
            # =========================
            p_home = implied_prob(odds[home]) * (1 + sentiment(home) - injury(home))
            p_away = implied_prob(odds[away]) * (1 + sentiment(away) - injury(away))

            # normalize
            total = p_home + p_away
            p_home /= total
            p_away /= total

            # =========================
            # PICK
            # =========================
            if ev(p_home, odds[home]) > ev(p_away, odds[away]):
                pick = home
                p = p_home
                odds_used = odds[home]
            else:
                pick = away
                p = p_away
                odds_used = odds[away]

            ev_v = ev(p, odds_used)
            clv_v = clv_proxy(odds_used)

            mom = momentum(pick)
            sent = sentiment(pick)
            inj = injury(pick)

            alpha = alpha_score(ev_v, clv_v, mom, sent, inj)

            # =========================
            # FILTER
            # =========================
            if alpha < 0.05:
                continue

            # =========================
            # PORTFOLIO
            # =========================
            k = kelly(p, odds_used)
            stake = min(k * bankroll, exposure_limit(bankroll, exposure))
            exposure += stake

            # =========================
            # SIM PnL
            # =========================
            win = np.random.rand() < p
            pnl = stake * (odds_used - 1) if win else -stake
            bankroll += pnl

            c.execute("""
                INSERT INTO trades VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                str(datetime.now()),
                f"{home} vs {away}",
                pick,
                odds_used,
                alpha,
                ev_v,
                pnl,
                exposure
            ))
            conn.commit()

            results.append({
                "Match": f"{home} vs {away}",
                "Time": taipei(dt).strftime("%Y-%m-%d %H:%M"),
                "Pick": pick,
                "Odds": odds_used,
                "Prob": round(p, 3),
                "EV": round(ev_v, 3),
                "Alpha": round(alpha, 4),
                "Stake": round(stake, 2),
                "PnL": round(pnl, 2)
            })

        except:
            continue

    df = pd.DataFrame(results)

    if df.empty:
        st.warning("⚠️ No institutional edge detected")
        st.stop()

    df = df.sort_values("Alpha", ascending=False)

    st.success(f"💰 Desk Active | Trades: {len(df)}")

    st.dataframe(df, use_container_width=True)

    st.subheader("📊 Desk Summary")

    st.write({
        "Avg Alpha": df["Alpha"].mean(),
        "Avg EV": df["EV"].mean(),
        "Bankroll": bankroll,
        "Exposure": exposure
    })
