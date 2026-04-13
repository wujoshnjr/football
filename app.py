import streamlit as st
from football.engine import FootballTradingEngine
from datetime import datetime, timedelta
import pytz
import random

st.set_page_config(layout="wide")

st.title("⚽ Football Trading System v5 (Hedge Fund)")

engine = FootballTradingEngine()

# 🔥 模擬更多場次（解決你說場次太少）
teams = [
    "Man City", "Arsenal", "Liverpool", "Chelsea",
    "Barcelona", "Real Madrid", "Atletico Madrid",
    "Bayern", "Dortmund", "Leipzig",
    "PSG", "Marseille", "Lyon",
    "Inter", "Juventus", "Milan",
    "Napoli", "Roma", "Lazio"
]

matches = []

for i in range(20):  # 🔥 20場（可再加）
    home = random.choice(teams)
    away = random.choice([t for t in teams if t != home])

    kickoff = datetime.utcnow() + timedelta(hours=i)

    matches.append((home, away, kickoff))

# 🔥 台北時間轉換（你要求的）
tz = pytz.timezone("Asia/Taipei")

# =========================================
# 顯示比賽（專業版 UI）
# =========================================

for home, away, kickoff in matches:

    result = engine.predict(home, away)

    kickoff_tpe = kickoff.replace(tzinfo=pytz.utc).astimezone(tz)

    with st.container():
        col1, col2, col3 = st.columns([3,1,1])

        # 🔥 球隊顯示（修正你一直講的問題）
        with col1:
            st.markdown(f"""
            ### 🏟️ {result['home_team']} vs {result['away_team']}
            ⏰ 開賽時間（台北）: {kickoff_tpe.strftime('%m-%d %H:%M')}
            """)

        # 🔥 勝率
        with col2:
            st.metric("Home", f"{result['home_prob']:.1%}")
            st.metric("Draw", f"{result['draw_prob']:.1%}")
            st.metric("Away", f"{result['away_prob']:.1%}")

        # 🔥 Over/Under
        with col3:
            st.metric("Over 2.5", f"{result['over25']:.1%}")

        # 🔥 比分預測（你一直要的）
        st.markdown("**Top Score Predictions**")

        for score, count in result["top_scores"]:
            st.write(f"{score}")

        st.markdown("---")
