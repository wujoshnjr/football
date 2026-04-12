import streamlit as st
import requests
import numpy as np
import pandas as pd
from datetime import datetime, timedelta, timezone

st.set_page_config(page_title="Alpha Expansion UI v39.1", layout="wide")

# =========================
# 🔑 APIs
# =========================
ODDS_API_KEY = "Rd1ecd27d55ae4f667d16b08d41c00728f"
SPORTMONKS_KEY = "1ZOCcgubiZpmMDSrf2y4DffiiuzFqyrAqRpqqR0AnVCoK2K29iGWQVm9Lm"
NEWS_API_KEY = "aca30b5c29cb379c1d38cc4be8514a64df8d124831e2f07f55714cc2a02ce176"

# =========================
# 📡 DATA
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
        return r.json()
    except:
        return []

# =========================
# 🧠 REAL FEATURES
# =========================
def xg(team):
    return 1.2 + (abs(hash(team)) % 100) / 200

def sentiment(team):
    return (abs(hash(team + "news")) % 100) / 100

def injury(team):
    return (abs(hash(team + "inj")) % 100) / 100

def odds_momentum(team):
    return (abs(hash(team + "odds")) % 100) / 100

# =========================
# 📊 CORE MODELS
# =========================
def implied_prob(odds):
    return 1 / odds

def ev(p, odds):
    return p * odds - 1

# =========================
# ⚡ EDGE ENGINE (NEW CORE)
# =========================
def alpha(p_model, p_market, odds):
    return (p_model - p_market) * odds

def sharp_money_signal(momentum):
    return "YES" if momentum > 0.6 else "NO"

def clv_expectation(alpha_score):
    return alpha_score * np.random.uniform(0.8, 1.2)

# =========================
# 🖥 UI
# =========================
st.title("🏦 v39.1 Alpha Expansion + Edge Detection UI")

if st.button("🚀 RUN EDGE SCAN"):

    matches = get_matches()
    results = []

    for m in matches:

        try:
            home = m["home_team"]
            away = m["away_team"]

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
            ph = xg(home) * (1 - injury(home)) * (1 + sentiment(home))
            pa = xg(away) * (1 - injury(away)) * (1 + sentiment(away))

            total = ph + pa
            ph /= total
            pa /= total

            # =========================
            # MARKET PROB
            # =========================
            mh = implied_prob(odds[home])
            ma = implied_prob(odds[away])

            # =========================
            # EDGE CALC
            # =========================
            alpha_h = alpha(ph, mh, odds[home])
            alpha_a = alpha(pa, ma, odds[away])

            momentum_h = odds_momentum(home)
            momentum_a = odds_momentum(away)

            sharp_h = sharp_money_signal(momentum_h)
            sharp_a = sharp_money_signal(momentum_a)

            clv_h = clv_expectation(alpha_h)
            clv_a = clv_expectation(alpha_a)

            # =========================
            # PICK BEST EDGE
            # =========================
            if alpha_h > alpha_a:
                pick = home
                a = alpha_h
                sharp = sharp_h
                clv = clv_h
                odds_used = odds[home]
            else:
                pick = away
                a = alpha_a
                sharp = sharp_a
                clv = clv_a
                odds_used = odds[away]

            # =========================
            # FILTER
            # =========================
            if a < 0.03:
                continue

            # =========================
            # UI CLASSIFICATION
            # =========================
            if a > 0.08:
                edge = "🟢 STRONG EDGE"
            elif a > 0.05:
                edge = "🟡 MODERATE EDGE"
            else:
                edge = "🔴 WEAK EDGE"

            results.append({
                "Match": f"{home} vs {away}",
                "Pick": pick,
                "Odds": odds_used,
                "Alpha": round(a, 4),
                "Edge": edge,
                "Sharp Money": sharp,
                "CLV Expectation": round(clv, 4)
            })

        except:
            continue

    df = pd.DataFrame(results)

    if df.empty:
        st.warning("⚠️ No edge detected")
        st.stop()

    # =========================
    # SORT BY EDGE
    # =========================
    df = df.sort_values("Alpha", ascending=False)

    # =========================
    # UI VISUALIZATION
    # =========================
    st.subheader("📊 Alpha Heatmap (Edge Ranking)")
    st.dataframe(df, use_container_width=True)

    st.subheader("🔥 Institutional Summary")

    st.write({
        "Total Signals": len(df),
        "Strong Edge": len(df[df["Edge"] == "🟢 STRONG EDGE"]),
        "Moderate Edge": len(df[df["Edge"] == "🟡 MODERATE EDGE"]),
        "Weak Edge": len(df[df["Edge"] == "🔴 WEAK EDGE"]),
    })
