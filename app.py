# ============================================
# FOOTBALL TRADING SYSTEM - FINAL UPGRADED VERSION
# ============================================

import os
import asyncio
import logging
from datetime import datetime, timedelta
from dataclasses import dataclass
from enum import Enum
from typing import Dict, List, Optional

import numpy as np
import pandas as pd
import streamlit as st
from scipy import stats
import pytz

# safe import (避免 Streamlit crash)
try:
    import aiohttp
    AIOHTTP_OK = True
except Exception:
    AIOHTTP_OK = False

# ============================================
# LOGGING
# ============================================

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("football_engine")

# ============================================
# ENUMS
# ============================================

class TrapSignal(Enum):
    OK = "OK"
    WARNING = "WARNING"
    TRAP = "TRAP"

# ============================================
# DATA MODELS
# ============================================

@dataclass
class TeamStats:
    name: str
    attack: float = 1.0
    defense: float = 1.0
    form: float = 1.0
    elo: float = 1500
    rest_days: float = 5.0
    xg_for: float = 1.4
    xg_against: float = 1.2
    tempo: float = 1.0
    injury: float = 1.0

@dataclass
class Odds:
    home: float
    draw: float
    away: float

# ============================================
# CORE MODEL (UPGRADED POISSON)
# ============================================

class PoissonEngine:
    def __init__(self):
        self.league_avg = 2.7

    def lambda_team(self, t: TeamStats, opp: TeamStats, home: bool):
        home_bonus = 1.15 if home else 1.0

        elo_factor = (t.elo - opp.elo) / 400
        elo_factor = np.clip(1 + elo_factor * 0.1, 0.8, 1.2)

        xg_factor = t.xg_for / max(opp.xg_against, 0.1)

        form_factor = t.form
        injury_factor = t.injury

        tempo_factor = t.tempo

        lam = (
            self.league_avg / 2
            * t.attack
            * opp.defense
            * home_bonus
            * elo_factor
            * xg_factor
            * form_factor
            * injury_factor
            * tempo_factor
        )

        return np.clip(lam, 0.2, 4.5)

    def score_matrix(self, lh, la):
        max_g = 7
        mat = {}

        for i in range(max_g):
            for j in range(max_g):
                p = stats.poisson.pmf(i, lh) * stats.poisson.pmf(j, la)
                mat[f"{i}-{j}"] = p

        return mat

# ============================================
# MONTE CARLO SIM
# ============================================

class Simulator:
    def run(self, lh, la, n=50000):
        hg = np.random.poisson(lh, n)
        ag = np.random.poisson(la, n)

        return {
            "home": np.mean(hg > ag),
            "draw": np.mean(hg == ag),
            "away": np.mean(hg < ag),
            "hg": np.mean(hg),
            "ag": np.mean(ag),
            "over25": np.mean(hg + ag > 2.5),
        }

# ============================================
# VALUE & KELLY
# ============================================

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

class TrapDetector:
    def detect(self, model, market):
        diff = abs(model["home"] - market["home"])

        if diff < 0.05:
            return TrapSignal.OK, diff
        elif diff < 0.12:
            return TrapSignal.WARNING, diff
        return TrapSignal.TRAP, diff

# ============================================
# ENGINE
# ============================================

class Engine:
    def __init__(self):
        self.poisson = PoissonEngine()
        self.sim = Simulator()
        self.kelly = Kelly()
        self.trap = TrapDetector()

    def analyze(self, home, away, odds):

        lh = self.poisson.lambda_team(home, away, True)
        la = self.poisson.lambda_team(away, home, False)

        sim = self.sim.run(lh, la)

        trap, score = self.trap.detect(sim, {
            "home": 1/odds.home,
            "draw": 1/odds.draw,
            "away": 1/odds.away
        })

        return {
            "lambda_home": lh,
            "lambda_away": la,
            "sim": sim,
            "trap": trap.value,
            "trap_score": score,
            "kelly_home": self.kelly.stake(sim["home"], odds.home),
            "kelly_away": self.kelly.stake(sim["away"], odds.away),
        }

# ============================================
# STREAMLIT UI (PRO DASHBOARD STYLE)
# ============================================

def run_ui():

    st.set_page_config(page_title="Football Trading Desk", layout="wide")

    st.title("⚽ Football Trading System (UPGRADED)")

    engine = Engine()

    # demo teams (professional factors included)
    home = TeamStats(
        "Man City", attack=1.3, defense=1.1, form=1.2,
        elo=1950, xg_for=2.3, xg_against=0.9, tempo=1.1
    )

    away = TeamStats(
        "Arsenal", attack=1.2, defense=1.0, form=1.05,
        elo=1880, xg_for=1.8, xg_against=1.1, tempo=1.0
    )

    odds = Odds(home=1.85, draw=3.6, away=4.2)

    if st.button("RUN ANALYSIS"):
        result = engine.analyze(home, away, odds)

        col1, col2, col3 = st.columns(3)

        col1.metric("Home Lambda", f"{result['lambda_home']:.2f}")
        col2.metric("Away Lambda", f"{result['lambda_away']:.2f}")
        col3.metric("Trap Signal", result["trap"])

        st.subheader("Simulation Probabilities")
        st.json(result["sim"])

        st.subheader("Kelly Stakes")
        st.write(result["kelly_home"], result["kelly_away"])

        st.subheader("Trap Score")
        st.write(result["trap_score"])


if __name__ == "__main__":
    run_ui()
