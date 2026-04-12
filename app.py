# ============================================
# FOOTBALL TRADING SYSTEM v3 (FULL FIXED)
# ============================================

import streamlit as st
import numpy as np
import pandas as pd
from dataclasses import dataclass
from enum import Enum
from scipy import stats

# ============================================
# ENUMS
# ============================================

class TrapSignal(Enum):
    OK = "OK"
    WARNING = "WARNING"
    TRAP_HOME = "TRAP_HOME"
    TRAP_AWAY = "TRAP_AWAY"
    TRAP_DRAW = "TRAP_DRAW"

# ============================================
# DATA
# ============================================

@dataclass
class Match:
    home: str
    away: str
    league: str
    odds_h: float
    odds_d: float
    odds_a: float

# ============================================
# CORE ENGINE
# ============================================

class Engine:

    def poisson_lambda(self, base=1.5):
        return np.random.uniform(1.0, 2.5)

    def simulate(self, lh, la, n=5000):

        home = np.random.poisson(lh, n)
        away = np.random.poisson(la, n)

        return {
            "home_win": np.mean(home > away),
            "draw": np.mean(home == away),
            "away_win": np.mean(home < away),
            "over25": np.mean((home + away) > 2.5),
            "btts": np.mean((home > 0) & (away > 0)),
            "home_goals": np.mean(home),
            "away_goals": np.mean(away),
        }

    def kelly(self, prob, odds):
        b = odds - 1
        return max(0, (b*prob - (1-prob)) / b)

    def trap(self, sim, odds):

        market_home = 1/odds.odds_h
        model_home = sim["home_win"]

        diff = abs(market_home - model_home)

        if diff < 0.05:
            return TrapSignal.OK, diff
        elif diff < 0.12:
            return TrapSignal.WARNING, diff
        else:
            return TrapSignal.TRAP_HOME, diff

    def run(self, match: Match):

        lh = self.poisson_lambda()
        la = self.poisson_lambda()

        sim = self.simulate(lh, la)

        trap, score = self.trap(sim, match)

        return {
            "sim": sim,
            "trap": trap,
            "trap_score": score,

            "kelly_home": self.kelly(sim["home_win"], match.odds_h),
            "kelly_draw": self.kelly(sim["draw"], match.odds_d),
            "kelly_away": self.kelly(sim["away_win"], match.odds_a),
        }

# ============================================
# UI
# ============================================

st.set_page_config(layout="wide")

engine = Engine()

st.title("⚽ Football Trading System v3 (FULL FIXED)")

# =========================
# FIXTURES (IMPORTANT)
# =========================

fixtures = [
    Match("Man City", "Arsenal", "EPL", 1.85, 3.6, 4.2),
    Match("Real Madrid", "Barcelona", "La Liga", 1.95, 3.4, 3.8),
    Match("Bayern", "Dortmund", "Bundesliga", 1.70, 4.0, 4.5),
]

# =========================
# RUN
# =========================

results = []

for m in fixtures:
    res = engine.run(m)
    results.append((m, res))

# =========================
# DISPLAY
# =========================

for match, res in results:

    st.markdown("---")

    st.subheader(f"{match.home} vs {match.away}")
    st.caption(match.league)

    # probs
    c1, c2, c3 = st.columns(3)

    c1.metric("Home", f"{res['sim']['home_win']:.1%}")
    c2.metric("Draw", f"{res['sim']['draw']:.1%}")
    c3.metric("Away", f"{res['sim']['away_win']:.1%}")

    # goals
    st.write("Expected Goals:")
    st.write(f"Home: {res['sim']['home_goals']:.2f}")
    st.write(f"Away: {res['sim']['away_goals']:.2f}")

    # kelly
    k1, k2, k3 = st.columns(3)

    k1.metric("Kelly Home", f"{res['kelly_home']:.2%}")
    k2.metric("Kelly Draw", f"{res['kelly_draw']:.2%}")
    k3.metric("Kelly Away", f"{res['kelly_away']:.2%}")

    # trap
    st.write("Trap Signal:", res["trap"].value, "score:", round(res["trap_score"], 3))

    if res["trap"] == TrapSignal.OK:
        st.success("SAFE")
    else:
        st.error("POTENTIAL TRAP / VALUE SHIFT")
