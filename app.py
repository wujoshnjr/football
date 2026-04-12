# ============================================
# INSTITUTIONAL FOOTBALL TRADING SYSTEM v5.2
# FULL HEDGE FUND ENGINE (FIXED + COMPLETE)
# ============================================

import os
import asyncio
import numpy as np
import pandas as pd
import streamlit as st
import pytz

from datetime import datetime, timedelta
from dataclasses import dataclass, field
from enum import Enum
from scipy import stats

# ============================================
# TIMEZONE (TAIPEI FIX)
# ============================================

TZ_TPE = pytz.timezone("Asia/Taipei")

def to_tpe(dt: datetime):
    if dt is None:
        return "TBD"
    return dt.astimezone(TZ_TPE).strftime("%Y-%m-%d %H:%M")

# ============================================
# ENUMS
# ============================================

class TrapSignal(Enum):
    OK = "OK"
    WARNING = "WARNING"
    TRAP_HOME = "TRAP_HOME"
    TRAP_AWAY = "TRAP_AWAY"

# ============================================
# DATA STRUCTURES
# ============================================

@dataclass
class TeamStats:
    team_name: str
    attack_strength: float = 1.0
    defense_strength: float = 1.0
    home_advantage: float = 1.15
    form_5: float = 1.0
    form_10: float = 1.0
    h2h: float = 0.0
    injury: float = 1.0

@dataclass
class Odds:
    home: float
    draw: float
    away: float

@dataclass
class Match:
    home: TeamStats
    away: TeamStats
    odds: Odds
    kickoff: datetime

# ============================================
# POISSON MODEL (ENHANCED)
# ============================================

class PoissonModel:

    def lambda_goal(self, team, opp, is_home, market=None):

        base = (
            team.attack_strength *
            opp.defense_strength *
            1.35
        )

        home_boost = team.home_advantage if is_home else 1.0

        form = (team.form_5 * 0.6 + team.form_10 * 0.4)

        h2h = 1 + team.h2h * 0.1

        injury = team.injury

        market_factor = 1.0
        if market:
            market_factor = 1 + (market["home"] - 0.5) * 0.4

        return max(0.2, min(5.0,
            base * home_boost * form * h2h * injury * market_factor
        ))

# ============================================
# MONTE CARLO (100,000 SIMULATION)
# ============================================

class MonteCarlo:

    def run(self, hl, al, n=100000):

        home = np.random.poisson(hl, n)
        away = np.random.poisson(al, n)

        total = home + away

        return {
            "home": np.mean(home > away),
            "draw": np.mean(home == away),
            "away": np.mean(home < away),

            "over25": np.mean(total > 2.5),
            "over35": np.mean(total > 3.5),

            "score": {
                f"{h}-{a}": np.mean((home == h) & (away == a))
                for h in range(6) for a in range(6)
            }
        }

# ============================================
# TRAP DETECTOR
# ============================================

class TrapDetector:

    def detect(self, model, market):

        div = abs(model["home"] - market["home"])

        if div < 0.1:
            return TrapSignal.OK, div

        if div < 0.2:
            return TrapSignal.WARNING, div

        return TrapSignal.TRAP_HOME, div

# ============================================
# KELLY
# ============================================

class Kelly:

    def calc(self, p, odds):

        if odds <= 1:
            return 0

        b = odds - 1
        q = 1 - p

        k = (b * p - q) / b

        return max(0, min(k, 0.05))

# ============================================
# ENGINE
# ============================================

class Engine:

    def analyze(self, match: Match):

        market = {
            "home": 1 / match.odds.home,
            "draw": 1 / match.odds.draw,
            "away": 1 / match.odds.away
        }

        model = PoissonModel()

        hl = model.lambda_goal(match.home, match.away, True, market)
        al = model.lambda_goal(match.away, match.home, False, market)

        mc = MonteCarlo().run(hl, al)

        trap, trap_score = TrapDetector().detect(mc, market)

        ev = {
            "home": mc["home"] * match.odds.home - 1,
            "draw": mc["draw"] * match.odds.draw - 1,
            "away": mc["away"] * match.odds.away - 1
        }

        kelly = Kelly()

        stake = {
            "home": kelly.calc(mc["home"], match.odds.home),
            "draw": kelly.calc(mc["draw"], match.odds.draw),
            "away": kelly.calc(mc["away"], match.odds.away)
        }

        best = max(ev.items(), key=lambda x: x[1])

        return {
            "home_prob": mc["home"],
            "draw_prob": mc["draw"],
            "away_prob": mc["away"],

            "xg_home": hl,
            "xg_away": al,

            "score": mc["score"],

            "ev": ev,
            "kelly": stake,

            "trap": trap.value,
            "trap_score": trap_score,

            "best_bet": best,
        }

# ============================================
# STREAMLIT UI
# ============================================

def run_ui(match, result):

    st.title("🏦 Football Trading Desk v5.2")

    st.write("Kickoff (Taipei):", to_tpe(match.kickoff))

    col1, col2, col3 = st.columns(3)

    col1.metric("Home", f"{result['home_prob']:.1%}")
    col2.metric("Draw", f"{result['draw_prob']:.1%}")
    col3.metric("Away", f"{result['away_prob']:.1%}")

    st.markdown("### 🎯 Best Bet")
    st.success(result["best_bet"])

    st.markdown("### ⚠️ Trap Signal")
    st.warning(result["trap"])

    st.markdown("### 📊 Expected Goals")
    st.write(result["xg_home"], result["xg_away"])

    st.markdown("### 💰 EV")
    st.json(result["ev"])

# ============================================
# MAIN
# ============================================

def main():

    home = TeamStats("Home", 1.2, 0.9, 1.15, 1.1, 1.05)
    away = TeamStats("Away", 1.1, 1.0, 1.0, 1.0, 1.0)

    match = Match(
        home=home,
        away=away,
        odds=Odds(1.9, 3.4, 4.0),
        kickoff=datetime(2026, 4, 13, 20, 0, tzinfo=pytz.utc)
    )

    engine = Engine()
    result = engine.analyze(match)

    run_ui(match, result)

if __name__ == "__main__":
    main()
