import streamlit as st
import numpy as np
import requests
import datetime as dt
from zoneinfo import ZoneInfo

TAIPEI = ZoneInfo("Asia/Taipei")

# =========================
# FALLBACK (LAST RESORT ONLY)
# =========================
def fallback():
    return [{
        "home_team": "Fallback FC",
        "away_team": "Test United",
        "commence_time": (dt.datetime.now(TAIPEI) + dt.timedelta(hours=2)).isoformat(),
        "bookmakers": [{
            "markets": [{
                "outcomes": [
                    {"price": 2.0},
                    {"price": 3.2},
                    {"price": 3.6}
                ]
            }]
        }]
    }]

# =========================
# PRIMARY DATA
# =========================
def fetch_primary():

    try:
        r = requests.get(
            "https://api.the-odds-api.com/v4/sports/soccer_epl/odds",
            params={
                "api_key": st.secrets["API_KEYS"]["ODDS_API"],
                "regions": "eu",
                "markets": "h2h",
                "oddsFormat": "decimal"
            },
            timeout=10
        )

        if r.status_code != 200:
            return []

        return r.json()

    except:
        return []

# =========================
# DATA PIPELINE (NEW CORE)
# =========================
def load_data():

    data = fetch_primary()

    if data:
        return data, "PRIMARY"

    return fallback(), "FALLBACK"

# =========================
# SAFE PARSER
# =========================
def parse_odds(m):

    try:
        outs = m.get("bookmakers", [])[0].get("markets", [])[0].get("outcomes", [])
        return [o["price"] for o in outs]
    except:
        return None

# =========================
# SIGNAL ENGINE
# =========================
def signal(odds):

    probs = np.array([1/o for o in odds])
    probs = probs / probs.sum()

    return probs, (max(probs) - 0.33) * 3

# =========================
# APP
# =========================
st.title("🏦 v28 REAL PRODUCTION HEDGE FUND SYSTEM")

data, source = load_data()

st.info(f"DATA SOURCE: {source} | MATCHES: {len(data)}")

for m in data:

    home = m.get("home_team")
    away = m.get("away_team")

    st.markdown("━━━━━━━━━━━━━━━━━━")
    st.subheader(f"{away} vs {home}")

    odds = parse_odds(m)

    if not odds:
        st.warning("No odds → display only")
        continue

    probs, sig = signal(odds)

    st.metric("Signal", round(sig, 4))

    st.write({
        "HOME": round(probs[0], 3),
        "DRAW": round(probs[1], 3),
        "AWAY": round(probs[2], 3),
    })

st.success("SYSTEM RUNNING (NO EMPTY STATE GUARANTEE)")
