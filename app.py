# ============================================
# INSTITUTIONAL FOOTBALL TRADING SYSTEM (FIXED + UPGRADED)
# ============================================

import os
import numpy as np
import pandas as pd
import streamlit as st
from dataclasses import dataclass, field
from enum import Enum
from datetime import datetime, timedelta
from scipy import stats
import pytz

# =========================
# ENUMS
# =========================

class TrapSignal(Enum):
    OK = "OK"
    WARNING = "WARNING"
    TRAP_HOME = "TRAP_HOME"
    TRAP_AWAY = "TRAP_AWAY"
    TRAP_DRAW = "TRAP_DRAW"

# =========================
# DATA STRUCTURES
# =========================

@dataclass
class TeamStats:
    attack: float = 1.0
    defense: float = 1.0
    form: float = 1.0
    xg_for: float = 1.5
    xg_against: float = 1.2
    injury: float = 1.0
    fatigue: float = 1.0
    motivation: float = 1.0
    coach_rating: float = 1.0
    home_adv: float = 1.1

@dataclass
class Match:
    home: str
    away: str
    league: str
    odds_home: float
    odds_draw: float
    odds_away: float

# =========================
# MARKET ENGINE
# =========================

class MarketEngine:

    @staticmethod
    def implied_probs(odds):
        total = sum(1/o for o in odds)
        return [(1/o)/total for o in odds]

# =========================
# POISSON MODEL (UPGRADED)
# =========================

class PoissonModel:

    def lambda_team(self, team: TeamStats, opp: TeamStats, home: bool):

        base = (
            team.attack * opp.defense *
            team.xg_for / max(opp.xg_against, 0.1)
        )

        home_bonus = team.home_adv if home else 1.0

        form_factor = (team.form * 0.6 + team.motivation * 0.4)

        fatigue_penalty = 1 / max(team.fatigue, 0.5)

        injury_penalty = team.injury

        return base * home_bonus * form_factor * fatigue_penalty * injury_penalty

# =========================
# MONTE CARLO
# =========================

class Simulator:

    def simulate(self, lh, la, n=20000):

        hg = np.random.poisson(lh, n)
        ag = np.random.poisson(la, n)

        return {
            "home_win": np.mean(hg > ag),
            "draw": np.mean(hg == ag),
            "away_win": np.mean(hg < ag),
            "avg_goals": np.mean(hg + ag)
        }

# =========================
# TRAP DETECTOR (IMPROVED)
# =========================

class TrapDetector:

    def detect(self, model, market):

        diff = abs(model["home_win"] - market[0])

        if diff > 0.20:
            return TrapSignal.TRAP_HOME, diff
        elif diff > 0.12:
            return TrapSignal.WARNING, diff
        else:
            return TrapSignal.OK, diff

# =========================
# KELLY
# =========================

class Kelly:

    def calc(self, p, odds):
        b = odds - 1
        q = 1 - p
        return max(0, (b*p - q) / b)

# =========================
# ENGINE
# =========================

class Engine:

    def __init__(self):
        self.model = PoissonModel()
        self.sim = Simulator()
        self.trap = TrapDetector()
        self.kelly = Kelly()

    def run(self, match):

        home_stats = TeamStats()
        away_stats = TeamStats()

        lh = self.model.lambda_team(home_stats, away_stats, True)
        la = self.model.lambda_team(away_stats, home_stats, False)

        sim = self.sim.simulate(lh, la)

        market = MarketEngine.implied_probs([
            match.odds_home,
            match.odds_draw,
            match.odds_away
        ])

        trap_signal, trap_score = self.trap.detect(sim, market)

        return {
            "sim": sim,
            "trap": trap_signal,
            "trap_score": trap_score,
            "kelly_home": self.kelly.calc(sim["home_win"], match.odds_home),
            "kelly_draw": self.kelly.calc(sim["draw"], match.odds_draw),
            "kelly_away": self.kelly.calc(sim["away_win"], match.odds_away),
        }

# =========================
# STREAMLIT UI (UPGRADED)
# =========================

st.set_page_config(page_title="Football Trading System", layout="wide")

engine = Engine()

st.title("⚽ Institutional Football Trading System (UPGRADED)")

match = Match(
    home="Team A",
    away="Team B",
    league="EPL",
    odds_home=1.90,
    odds_draw=3.40,
    odds_away=4.20
)

if st.button("RUN MODEL"):
    result = engine.run(match)

    st.subheader("📊 Prediction")
    st.write(result["sim"])

    st.subheader("🚨 Trap Signal")
    st.write(result["trap"].value)
    st.write("Score:", result["trap_score"])

    st.subheader("💰 Kelly Stakes")
    st.write(result["kelly_home"], result["kelly_draw"], result["kelly_away"])
