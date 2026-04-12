# ============================================
# INSTITUTIONAL FOOTBALL TRADING SYSTEM v5.2
# FULL HEDGE FUND ENGINE - FINAL FIXED VERSION
# ============================================

import os
import asyncio
import numpy as np
import pandas as pd
import streamlit as st
import pytz

from datetime import datetime, timedelta
from dataclasses import dataclass
from enum import Enum
from scipy import stats

# ============================================
# TIMEZONE FIX (TAIPEI)
# ============================================

TZ_TPE = pytz.timezone("Asia/Taipei")

def fmt_time(dt):
    if not dt:
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
class Team:
    name: str
    attack: float = 1.0
    defense: float = 1.0
    form5: float = 1.0
    form10: float = 1.0
    home_adv: float = 1.15
    injury: float = 1.0
    h2h: float = 0.0

@dataclass
class Odds:
    home: float
    draw: float
    away: float

@dataclass
class Match:
    home: Team
    away: Team
    odds: Odds
    kickoff: datetime
    league: str

# ============================================
# POISSON MODEL
# ============================================

class Poisson:

    def lambda_goal(self, t, o, is_home=True, market=None):

        base = t.attack * o.defense * 1.35

        home = t.home_adv if is_home else 1.0

        form = (t.form5 * 0.6 + t.form10 * 0.4)

        h2h = 1 + t.h2h * 0.1

        injury = t.injury

        market_factor = 1.0
        if market:
            market_factor = 1 + (market["home"] - 0.5) * 0.3

        return max(0.2, min(5.0,
            base * home * form * h2h * injury * market_factor
        ))

    def score_matrix(self, hl, al):
        res = {}
        for h in range(6):
            for a in range(6):
                p = stats.poisson.pmf(h, hl) * stats.poisson.pmf(a, al)
                res[f"{h}-{a}"] = p
        return res

# ============================================
# MONTE CARLO (100,000 SIMS)
# ============================================

class MonteCarlo:

    def run(self, hl, al, n=100000):

        h = np.random.poisson(hl, n)
        a = np.random.poisson(al, n)

        total = h + a

        return {
            "home": np.mean(h > a),
            "draw": np.mean(h == a),
            "away": np.mean(h < a),

            "over25": np.mean(total > 2.5),
            "over35": np.mean(total > 3.5),

            "score": {
                f"{i}-{j}": np.mean((h == i) & (a == j))
                for i in range(6) for j in range(6)
            },

            "std_h": np.std(h),
            "std_a": np.std(a)
        }

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
# TRAP DETECTOR
# ============================================

class Trap:

    def detect(self, model, market):

        diff = abs(model["home"] - market["home"])

        if diff < 0.1:
            return TrapSignal.OK, diff
        elif diff < 0.2:
            return TrapSignal.WARNING, diff
        return TrapSignal.TRAP_HOME, diff

# ============================================
# ENGINE
# ============================================

class Engine:

    def analyze(self, m: Match):

        market = {
            "home": 1 / m.odds.home,
            "draw": 1 / m.odds.draw,
            "away": 1 / m.odds.away
        }

        p = Poisson()

        hl = p.lambda_goal(m.home, m.away, True, market)
        al = p.lambda_goal(m.away, m.home, False, market)

        mc = MonteCarlo().run(hl, al)

        trap, score = Trap().detect(mc, market)

        ev = {
            "home": mc["home"] * m.odds.home - 1,
            "draw": mc["draw"] * m.odds.draw - 1,
            "away": mc["away"] * m.odds.away - 1
        }

        k = Kelly()

        stake = {
            "home": k.calc(mc["home"], m.odds.home),
            "draw": k.calc(mc["draw"], m.odds.draw),
            "away": k.calc(mc["away"], m.odds.away)
        }

        best = max(ev.items(), key=lambda x: x[1])

        return {
            "home": mc["home"],
            "draw": mc["draw"],
            "away": mc["away"],

            "xg_h": hl,
            "xg_a": al,

            "score": mc["score"],

            "ev": ev,
            "kelly": stake,

            "trap": trap.value,
            "trap_score": score,

            "best": best
        }

# ============================================
# STREAMLIT UI
# ============================================

def ui(match, r):

    st.title("🏦 Football Trading Desk v5.2 FINAL")

    st.write("Kickoff (Taipei):", fmt_time(match.kickoff))

    col1, col2, col3 = st.columns(3)

    col1.metric("Home", f"{r['home']:.1%}")
    col2.metric("Draw", f"{r['draw']:.1%}")
    col3.metric("Away", f"{r['away']:.1%}")

    st.markdown("## 🎯 Best Bet")
    st.success(r["best"])

    st.markdown("## ⚠️ Trap Signal")
    st.warning(f"{r['trap']} ({r['trap_score']:.2f})")

    st.markdown("## ⚽ xG")
    st.write(r["xg_h"], r["xg_a"])

    st.markdown("## 💰 EV")
    st.json(r["ev"])

    st.markdown("## 🎲 Score Prediction (Top)")
    top = sorted(r["score"].items(), key=lambda x: x[1], reverse=True)[:5]
    st.write(top)

# ============================================
# DEMO MATCHES
# ============================================

def demo():

    h = Team("Home", 1.2, 0.9, 1.1, 1.0)
    a = Team("Away", 1.0, 1.0, 1.0, 1.0)

    return Match(
        home=h,
        away=a,
        odds=Odds(1.9, 3.4, 4.2),
        kickoff=datetime(2026, 4, 13, 18, 0, tzinfo=pytz.utc),
        league="EPL"
    )

# ============================================
# MAIN
# ============================================

def main():

    m = demo()

    engine = Engine()
    result = engine.analyze(m)

    ui(m, result)

if __name__ == "__main__":
    main()
