# ============================================
# FOOTBALL TRADING SYSTEM - FULL FIXED VERSION
# SINGLE FILE / STREAMLIT READY
# ============================================

import os
import asyncio
import numpy as np
import pandas as pd
import streamlit as st
from dataclasses import dataclass, field
from enum import Enum
from datetime import datetime, timedelta
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
# DATA STRUCTURES
# ============================================

@dataclass
class TeamStats:
    team_name: str
    attack: float = 1.0
    defense: float = 1.0
    form: float = 1.0

@dataclass
class Match:
    home: TeamStats
    away: TeamStats
    odds_home: float
    odds_draw: float
    odds_away: float

# ============================================
# MODELS
# ============================================

class PoissonModel:
    def lambda_goal(self, attack, defense):
        return max(0.2, min(4.5, attack * defense * 1.3))

    def match(self, home: TeamStats, away: TeamStats):
        home_lambda = self.lambda_goal(home.attack, away.defense)
        away_lambda = self.lambda_goal(away.attack, home.defense)
        return home_lambda, away_lambda

class MonteCarlo:
    def simulate(self, hl, al, n=20000):
        hg = np.random.poisson(hl, n)
        ag = np.random.poisson(al, n)

        return {
            "home": np.mean(hg > ag),
            "draw": np.mean(hg == ag),
            "away": np.mean(hg < ag),
            "hg_avg": np.mean(hg),
            "ag_avg": np.mean(ag),
        }

class Kelly:
    def stake(self, prob, odds):
        if odds <= 1:
            return 0
        b = odds - 1
        q = 1 - prob
        k = (b * prob - q) / b
        return max(0, min(k, 0.05))

class TrapDetector:
    def detect(self, model_home, market_home):
        diff = abs(model_home - market_home)
        if diff < 0.05:
            return TrapSignal.OK
        if diff < 0.15:
            return TrapSignal.WARNING
        return TrapSignal.TRAP_HOME if model_home > market_home else TrapSignal.TRAP_AWAY

# ============================================
# ENGINE
# ============================================

class Engine:
    def __init__(self):
        self.poisson = PoissonModel()
        self.mc = MonteCarlo()
        self.kelly = Kelly()
        self.trap = TrapDetector()

    def run(self, match: Match):
        hl, al = self.poisson.match(match.home, match.away)

        sim = self.mc.simulate(hl, al)

        trap_signal = self.trap.detect(sim["home"], 1 / match.odds_home)

        return {
            "home_prob": sim["home"],
            "draw_prob": sim["draw"],
            "away_prob": sim["away"],
            "xg_home": sim["hg_avg"],
            "xg_away": sim["ag_avg"],
            "trap": trap_signal.value,
            "kelly_home": self.kelly.stake(sim["home"], match.odds_home),
            "kelly_away": self.kelly.stake(sim["away"], match.odds_away),
        }

# ============================================
# STREAMLIT UI
# ============================================

def main():
    st.title("⚽ Football Trading System (FIXED VERSION)")

    engine = Engine()

    # Demo match (避免 API crash)
    match = Match(
        home=TeamStats("Man City", 1.3, 0.9, 1.2),
        away=TeamStats("Arsenal", 1.1, 1.0, 1.1),
        odds_home=1.85,
        odds_draw=3.6,
        odds_away=4.2
    )

    if st.button("Run Model"):
        result = engine.run(match)

        st.subheader("📊 Prediction")

        st.write(result)

        col1, col2, col3 = st.columns(3)

        col1.metric("Home Win", f"{result['home_prob']:.1%}")
        col2.metric("Draw", f"{result['draw_prob']:.1%}")
        col3.metric("Away Win", f"{result['away_prob']:.1%}")

        st.markdown("---")

        st.subheader("📈 Expected Goals")
        st.write(f"Home xG: {result['xg_home']:.2f}")
        st.write(f"Away xG: {result['xg_away']:.2f}")

        st.markdown("---")

        st.subheader("🚨 Trap Signal")
        st.write(result["trap"])

        st.subheader("💰 Kelly Stakes")
        st.write(f"Home: {result['kelly_home']:.3f}")
        st.write(f"Away: {result['kelly_away']:.3f}")


if __name__ == "__main__":
    main()
