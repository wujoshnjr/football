# ============================================
# FOOTBALL TRADING SYSTEM V5 (FIXED + UPGRADED)
# Hedge Fund Prediction Engine
# ============================================

import os
import asyncio
import numpy as np
import pandas as pd
import streamlit as st
from datetime import datetime, timedelta
from dataclasses import dataclass, field
from enum import Enum
import pytz
from scipy import stats

# ============================================
# CONFIG
# ============================================

TZ = pytz.timezone("Asia/Taipei")

st.set_page_config(
    page_title="V5 Football Hedge Fund",
    layout="wide"
)

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
    name: str
    attack: float
    defense: float
    form: float
    home_adv: float = 1.15

@dataclass
class Match:
    home: TeamStats
    away: TeamStats
    league: str
    kickoff: datetime
    odds_home: float
    odds_draw: float
    odds_away: float

# ============================================
# MODEL ENGINE (FIXED)
# ============================================

class PoissonEngine:
    def lambda_goals(self, atk, dfn, home_adv=1.0):
        return max(0.2, min(4.5, atk * (1/dfn) * 2.5 * home_adv))

    def simulate_score(self, lh, la):
        max_g = 6
        matrix = {}
        for h in range(max_g):
            for a in range(max_g):
                p = stats.poisson.pmf(h, lh) * stats.poisson.pmf(a, la)
                matrix[f"{h}-{a}"] = p
        return matrix

class MonteCarlo:
    def run(self, lh, la, n=100000):
        hg = np.random.poisson(lh, n)
        ag = np.random.poisson(la, n)

        return {
            "home": np.mean(hg > ag),
            "draw": np.mean(hg == ag),
            "away": np.mean(hg < ag),
            "hg_mean": np.mean(hg),
            "ag_mean": np.mean(ag),
            "over25": np.mean(hg + ag > 2.5)
        }

class Kelly:
    def stake(self, prob, odds):
        if odds <= 1:
            return 0
        b = odds - 1
        q = 1 - prob
        k = (b * prob - q) / b
        return max(0, min(k, 0.05))

# ============================================
# TRAP DETECTOR
# ============================================

def detect_trap(model, odds):
    diff = abs(model["home"] - (1/odds.odds_home))
    if diff > 0.15:
        return TrapSignal.WARNING, diff
    return TrapSignal.OK, diff

# ============================================
# DEMO MATCHES (FIXED + MORE)
# ============================================

def load_matches():
    teams = [
        ("Man City", "Arsenal"),
        ("Real Madrid", "Barcelona"),
        ("Bayern", "Dortmund"),
        ("Inter", "AC Milan"),
        ("PSG", "Marseille"),
        ("Chelsea", "Liverpool"),
        ("Atletico", "Sevilla"),
        ("Juventus", "Napoli"),
        ("Ajax", "PSV"),
        ("Benfica", "Porto"),
        ("Dortmund", "Leipzig"),
        ("Tottenham", "Newcastle"),
    ]

    matches = []
    base = datetime.now(TZ)

    for i, (h, a) in enumerate(teams * 2):  # 🔥 increase matches
        match = Match(
            home=TeamStats(h, np.random.uniform(1.0,1.3), np.random.uniform(0.8,1.2), np.random.uniform(0.8,1.3)),
            away=TeamStats(a, np.random.uniform(1.0,1.3), np.random.uniform(0.8,1.2), np.random.uniform(0.8,1.3)),
            league="EURO",
            kickoff=base + timedelta(hours=i*3),
            odds_home=np.random.uniform(1.6,2.4),
            odds_draw=np.random.uniform(3.0,3.8),
            odds_away=np.random.uniform(2.8,4.5)
        )
        matches.append(match)

    return matches

# ============================================
# ENGINE RUN
# ============================================

poisson = PoissonEngine()
mc = MonteCarlo()
kelly = Kelly()

def analyze(match):
    lh = poisson.lambda_goals(match.home.attack, match.away.defense, match.home.home_adv)
    la = poisson.lambda_goals(match.away.attack, match.home.defense, 1.0)

    sim = mc.run(lh, la)

    trap, score = detect_trap(sim, match)

    ev_home = sim["home"] * match.odds_home - 1
    ev_draw = sim["draw"] * match.odds_draw - 1
    ev_away = sim["away"] * match.odds_away - 1

    return {
        "sim": sim,
        "trap": trap,
        "score": score,
        "ev": {"H": ev_home, "D": ev_draw, "A": ev_away},
        "kelly": {
            "H": kelly.stake(sim["home"], match.odds_home),
            "D": kelly.stake(sim["draw"], match.odds_draw),
            "A": kelly.stake(sim["away"], match.odds_away),
        },
        "lambda": (lh, la)
    }

# ============================================
# UI (IMPROVED)
# ============================================

def main():

    st.title("🏦 V5 Football Hedge Fund Trading System")

    matches = load_matches()

    st.sidebar.header("Controls")
    only_value = st.sidebar.checkbox("Only Value Bets", True)

    for m in matches:

        r = analyze(m)

        if only_value and max(r["ev"].values()) < 0:
            continue

        kickoff_str = m.kickoff.strftime("%Y-%m-%d %H:%M (TPE)")

        st.markdown("---")

        # HEADER
        col1, col2, col3 = st.columns([3,1,1])

        with col1:
            st.subheader(f"{m.home.name} vs {m.away.name}")
            st.caption(f"{m.league} | Kickoff: {kickoff_str}")

        with col2:
            st.metric("Trap", r["trap"].value, f"{r['score']:.2f}")

        with col3:
            st.metric("Over25", f"{r['sim']['over25']:.1%}")

        # PROBABILITIES
        c1,c2,c3 = st.columns(3)

        c1.metric("Home Win", f"{r['sim']['home']:.1%}")
        c2.metric("Draw", f"{r['sim']['draw']:.1%}")
        c3.metric("Away Win", f"{r['sim']['away']:.1%}")

        # EXPECTED GOALS
        st.write(f"⚽ xG Home: {r['lambda'][0]:.2f} | Away: {r['lambda'][1]:.2f}")

        # EV
        st.write("📊 EV:")
        st.write(r["ev"])

        # KELLY
        st.write("💰 Kelly:")
        st.write(r["kelly"])

        # SCORELINES
        scores = poisson.simulate_score(r["lambda"][0], r["lambda"][1])
        top = sorted(scores.items(), key=lambda x: x[1], reverse=True)[:5]

        st.write("🎯 Top Scorelines:")
        st.write(top)

if __name__ == "__main__":
    main()
