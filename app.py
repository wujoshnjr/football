import streamlit as st
import numpy as np
import requests
import datetime as dt
from zoneinfo import ZoneInfo

TAIPEI = ZoneInfo("Asia/Taipei")

# =========================
# TIME SAFE
# =========================
def now_taipei():
    return dt.datetime.now(TAIPEI)

def to_taipei(ts):
    try:
        t = pd.to_datetime(ts)
        if t.tzinfo is None:
            t = t.tz_localize("UTC")
        return t.tz_convert(TAIPEI)
    except:
        return None

def in_24h(k):
    return k and now_taipei() <= k <= now_taipei() + dt.timedelta(hours=24)

# =========================
# FETCH (NO FILTER)
# =========================
def fetch_all():
    key = st.secrets["API_KEYS"]["ODDS_API"]

    try:
        r = requests.get(
            "https://api.the-odds-api.com/v4/sports/soccer_epl/odds",
            params={
                "api_key": key,
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
# SAFE MARKET PARSER (FIX)
# =========================
def safe_odds(m):

    try:
        outs = m.get("bookmakers", [])[0].get("markets", [])[0].get("outcomes", [])
        if len(outs) < 3:
            return None

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
st.title("🏦 v25 REAL HEDGE FUND ROBUST SYSTEM (FIXED NO MATCH ISSUE)")

data = fetch_all()

shown = 0

for m in data:

    home = m.get("home_team")
    away = m.get("away_team")

    k = to_taipei(m.get("commence_time"))

    # ❗ NEVER SKIP DISPLAY
    odds = safe_odds(m)

    st.markdown("━━━━━━━━━━━━━━━━━━")
    st.subheader(f"{away} vs {home}")

    # TIME (SAFE)
    if k:
        st.write(f"🕒 台北時間：{k.strftime('%Y-%m-%d %H:%M')}")
    else:
        st.write("🕒 台北時間：⚠️ unavailable")

    # NO ODDS CASE
    if not odds:
        st.warning("⚠️ Odds missing → DISPLAY ONLY MODE")
        continue

    probs, sig = signal(odds)

    st.metric("Signal", round(sig, 4))

    st.write({
        "HOME": round(probs[0], 3),
        "DRAW": round(probs[1], 3),
        "AWAY": round(probs[2], 3),
    })

    shown += 1

st.info(f"Total matches shown: {shown}")
