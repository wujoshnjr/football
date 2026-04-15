import streamlit as st
import pandas as pd
import numpy as np
import requests
import sqlite3
from datetime import datetime

from football.model import TeamModel, build_matrix
from football.simulation import monte_carlo, calc_probs
from football.betting import edge, kelly

# =========================
# 🔑 讀取 Streamlit secrets
# =========================
SPORTMONKS = st.secrets.get("SPORTMONKS_API_KEY", "")
ODDS = st.secrets.get("ODDS_API_KEY", "")
NEWS = st.secrets.get("NEWS_API_KEY", "")
FDATA = st.secrets.get("FOOTBALL_DATA_API_KEY", "")
RAPID = st.secrets.get("RAPIDAPI_KEY", "")

# =========================
# 🗄️ DB
# =========================
def init_db():
    conn = sqlite3.connect("zeus_pro.db", check_same_thread=False)
    conn.execute("""
    CREATE TABLE IF NOT EXISTS bets(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        match TEXT,
        bet TEXT,
        prob REAL,
        odds REAL,
        edge REAL,
        stake REAL,
        sentiment REAL,
        timestamp DATETIME
    )
    """)
    return conn

conn = init_db()

# =========================
# 🌐 API（全部防炸）
# =========================

def safe_get(url, headers=None):
    try:
        res = requests.get(url, headers=headers, timeout=10)
        return res.json()
    except:
        return {}

def get_matches():
    if not SPORTMONKS:
        return []

    url = f"https://api.sportmonks.com/v3/football/fixtures?api_token={SPORTMONKS}"
    data = safe_get(url)

    matches = []
    for m in data.get("data", [])[:15]:
        try:
            matches.append({
                "home": m["participants"][0]["name"],
                "away": m["participants"][1]["name"]
            })
        except:
            continue

    return matches

def get_odds():
    if not ODDS:
        return {}

    url = f"https://api.the-odds-api.com/v4/sports/soccer_epl/odds/?apiKey={ODDS}"
    data = safe_get(url)

    odds_map = {}

    for g in data:
        try:
            home = g["home_team"]
            away = g["away_team"]

            outcomes = g["bookmakers"][0]["markets"][0]["outcomes"]

            odds_map[f"{home}-{away}"] = {
                "home": outcomes[0]["price"],
                "draw": outcomes[1]["price"],
                "away": outcomes[2]["price"]
            }
        except:
            continue

    return odds_map

def get_sentiment(team):
    if not NEWS:
        return 0

    url = f"https://newsapi.org/v2/everything?q={team}&apiKey={NEWS}"
    data = safe_get(url)

    articles = data.get("articles", [])

    score = 0
    for a in articles[:5]:
        title = str(a.get("title", "")).lower()

        if "win" in title or "strong" in title:
            score += 1
        elif "injury" in title or "loss" in title:
            score -= 1

    return score / 5 if articles else 0

# =========================
# 🧠 引擎
# =========================
def run_engine():

    model = TeamModel()

    # fallback training（避免空模型）
    dummy = [
        {"home":"A","away":"B","home_goals":2,"away_goals":1},
        {"home":"B","away":"A","home_goals":1,"away_goals":1},
    ]
    model.train(dummy)

    matches = get_matches()
    odds_map = get_odds()

    if not matches or not odds_map:
        return pd.DataFrame()

    rows = []

    for m in matches:
        home = m["home"]
        away = m["away"]
        key = f"{home}-{away}"

        if key not in odds_map:
            continue

        odds = odds_map[key]

        # 預測 λ
        lh, la = model.predict_lambda(home, away)

        if np.isnan(lh) or np.isnan(la) or lh <= 0:
            lh, la = 1.3, 1.0

        sims = monte_carlo(lh, la)

        if len(sims) == 0:
            continue

        ph, p_draw, pa = calc_probs(sims)

        probs = [ph, p_draw, pa]
        odds_list = [odds["home"], odds["draw"], odds["away"]]

        edges = [edge(p, o) for p, o in zip(probs, odds_list)]

        # 情緒
        sent = get_sentiment(home) - get_sentiment(away)
        edges = [e + sent * 0.02 for e in edges]

        best_idx = int(np.argmax(edges))

        rows.append({
            "match": f"{home} vs {away}",
            "bet": ["主","和","客"][best_idx],
            "prob": probs[best_idx],
            "odds": odds_list[best_idx],
            "edge": edges[best_idx],
            "sentiment": sent
        })

    return pd.DataFrame(rows)

# =========================
# 🖥️ UI
# =========================
def main():
    st.set_page_config(layout="wide")
    st.title("⚛️ ZEUS QUANT — FINAL VERSION")

    tab1, tab2 = st.tabs(["🎯 AUTO", "📚 HISTORY"])

    with tab1:

        if st.button("🚀 RUN SYSTEM"):

            df = run_engine()

            if df.empty:
                st.warning("⚠️ API 無資料或 Key 無效")
                return

            df = df.sort_values("edge", ascending=False)

            st.dataframe(df, use_container_width=True)

            best = df.iloc[0]

            stake = kelly(best["prob"], best["odds"])

            st.subheader("🔥 BEST BET")
            st.write(best)
            st.write(f"Kelly: {stake:.2%}")

            # 存DB
            conn.execute(
                "INSERT INTO bets(match,bet,prob,odds,edge,stake,sentiment,timestamp) VALUES (?,?,?,?,?,?,?,?)",
                (
                    best["match"],
                    best["bet"],
                    best["prob"],
                    best["odds"],
                    best["edge"],
                    stake,
                    best["sentiment"],
                    datetime.now()
                )
            )
            conn.commit()

    with tab2:
        try:
            df = pd.read_sql_query("SELECT * FROM bets ORDER BY timestamp DESC", conn)
            st.dataframe(df, use_container_width=True)
        except:
            st.write("沒有資料")

# =========================
# 🚀 RUN
# =========================
if __name__ == "__main__":
    main()
