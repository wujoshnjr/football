import streamlit as st
import numpy as np
import pandas as pd
from dataclasses import dataclass
from enum import Enum
from datetime import datetime
import pytz
from scipy.stats import poisson

# =========================
# TIME SYSTEM (FIXED TPE)
# =========================

TPE = pytz.timezone("Asia/Taipei")

def to_tpe(dt):
    """Convert kickoff → Taipei time"""
    if dt is None:
        return None
    if dt.tzinfo is None:
        dt = pytz.utc.localize(dt)
    return dt.astimezone(TPE)

def fmt_tpe(dt):
    dt = to_tpe(dt)
    return dt.strftime("%Y-%m-%d %H:%M (TPE)")

# =========================
# ENUMS
# =========================

class Signal(Enum):
    SAFE = "SAFE"
    WARNING = "WARNING"
    TRAP = "TRAP"

# =========================
# MATCH STRUCTURE
# =========================

@dataclass
class Match:
    home: str
    away: str
    league: str
    odds_h: float
    odds_d: float
    odds_a: float
    kickoff: datetime

# =========================
# BET ENGINE
# =========================

class BetEngine:

    def kelly(self, p, odds):
        b = odds - 1
        if b <= 0:
            return 0
        return max(0, (b * p - (1 - p)) / b)

    def recommend(self, match, sim):

        bets = [
            ("home", sim["home"], match.odds_h),
            ("draw", sim["draw"], match.odds_d),
            ("away", sim["away"], match.odds_a),
        ]

        scored = []

        for side, p, odds in bets:

            ev = p * odds - 1
            k = self.kelly(p, odds)

            score = ev * 0.7 + k * 0.3

            scored.append({
                "side": side,
                "prob": p,
                "odds": odds,
                "ev": ev,
                "kelly": k,
                "score": score
            })

        best = max(scored, key=lambda x: x["score"])

        return {"best": best, "all": scored}

# =========================
# ENGINE CORE
# =========================

class Engine:

    def __init__(self):
        self.reco = BetEngine()

    def xg(self):
        return np.random.uniform(1.1, 2.6)

    # 100K SIMULATION (CONFIRMED)
    def simulate(self, lh, la, n=100000):

        home = np.random.poisson(lh, n)
        away = np.random.poisson(la, n)

        total = home + away

        return {
            "home": np.mean(home > away),
            "draw": np.mean(home == away),
            "away": np.mean(home < away),

            "hg": np.mean(home),
            "ag": np.mean(away),

            "over15": np.mean(total > 1.5),
            "over25": np.mean(total > 2.5),
            "over35": np.mean(total > 3.5),

            "btts": np.mean((home > 0) & (away > 0)),

            "std": np.std(total)
        }

    # SCORE PREDICTION FIXED
    def score_matrix(self, lh, la, max_goals=6):

        matrix = {}

        for i in range(max_goals + 1):
            for j in range(max_goals + 1):
                matrix[f"{i}-{j}"] = poisson.pmf(i, lh) * poisson.pmf(j, la)

        return dict(sorted(matrix.items(), key=lambda x: x[1], reverse=True))

    # TRAP SYSTEM
    def trap(self, sim, match):

        market_home = 1 / match.odds_h
        diff = abs(sim["home"] - market_home)

        if diff > 0.18:
            return Signal.TRAP, diff
        elif diff > 0.10:
            return Signal.WARNING, diff
        return Signal.SAFE, diff

    # MAIN PIPELINE
    def run(self, m):

        lh = self.xg()
        la = self.xg()

        sim = self.simulate(lh, la)

        signal, score = self.trap(sim, m)

        reco = self.reco.recommend(m, sim)

        return {
            "sim": sim,
            "signal": signal,
            "trap_score": score,
            "scores": self.score_matrix(lh, la),
            "recommendation": reco
        }

# =========================
# STREAMLIT APP
# =========================

st.set_page_config(layout="wide")
st.title("🏦 FOOTBALL HEDGE FUND v5.1 FINAL (TPE FIXED)")

engine = Engine()

# =========================
# FIXTURES
# =========================

matches = [
    Match("Man City", "Arsenal", "EPL", 1.85, 3.60, 4.20,
          datetime.utcnow().replace(tzinfo=pytz.utc)),

    Match("Real Madrid", "Barcelona", "La Liga", 1.95, 3.40, 3.80,
          datetime.utcnow().replace(tzinfo=pytz.utc)),

    Match("Bayern", "Dortmund", "Bundesliga", 1.70, 4.00, 4.50,
          datetime.utcnow().replace(tzinfo=pytz.utc)),
]

results = [(m, engine.run(m)) for m in matches]

# =========================
# TABLE VIEW
# =========================

st.subheader("📅 Matches")

df = pd.DataFrame([
    {
        "Match": f"{m.home} vs {m.away}",
        "League": m.league,
        "Kickoff (TPE)": fmt_tpe(m.kickoff),

        "Home": r["sim"]["home"],
        "Draw": r["sim"]["draw"],
        "Away": r["sim"]["away"],

        "Signal": r["signal"].value,
        "Trap Score": r["trap_score"]
    }
    for m, r in results
])

st.dataframe(df, use_container_width=True)

# =========================
# MATCH CARDS
# =========================

for m, r in results:

    st.markdown("---")

    st.subheader(f"{m.home} vs {m.away}")
    st.caption(f"{m.league} | ⏰ {fmt_tpe(m.kickoff)}")

    # PROBABILITY
    c1, c2, c3 = st.columns(3)
    c1.metric("Home", f"{r['sim']['home']:.1%}")
    c2.metric("Draw", f"{r['sim']['draw']:.1%}")
    c3.metric("Away", f"{r['sim']['away']:.1%}")

    # EXPECTED GOALS
    st.write("📊 Expected Goals")
    st.write(f"Home: {r['sim']['hg']:.2f}")
    st.write(f"Away: {r['sim']['ag']:.2f}")

    # OVER UNDER
    st.write("📉 Markets")
    st.write(f"O1.5: {r['sim']['over15']:.1%}")
    st.write(f"O2.5: {r['sim']['over25']:.1%}")
    st.write(f"O3.5: {r['sim']['over35']:.1%}")
    st.write(f"BTTS: {r['sim']['btts']:.1%}")

    # SCORE PREDICTION
    st.write("⚽ Score Prediction (Top 5)")

    for s, p in list(r["scores"].items())[:5]:
        st.write(f"{s}: {p:.2%}")

    # =========================
    # RECOMMENDATION (NEW CORE)
    # =========================

    best = r["recommendation"]["best"]

    st.markdown("### 🎯 Recommended Bet")

    st.success(f"""
**{best['side'].upper()}**
- Probability: {best['prob']:.1%}
- Odds: {best['odds']:.2f}
- EV: {best['ev']:+.2%}
- Kelly: {best['kelly']:.2%}
""")

    st.info(f"Score: {best['score']:.4f}")

    # =========================
    # SIGNAL
    # =========================

    if r["signal"] == Signal.SAFE:
        st.success("SAFE")
    elif r["signal"] == Signal.WARNING:
        st.warning("WARNING")
    else:
        st.error("TRAP DETECTED")
