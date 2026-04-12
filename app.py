# ============================================
# FOOTBALL TRADING SYSTEM v2 (UPGRADED)
# Production-Ready + Streamlit Optimized
# ============================================

import os
import asyncio
import aiohttp
import numpy as np
import pandas as pd
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any, Tuple
from enum import Enum
from datetime import datetime, timedelta
import streamlit as st
from scipy import stats
import logging
import pytz

# ============================================
# CONFIG
# ============================================

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("FTS")

# ============================================
# ENUMS
# ============================================

class TrapSignal(Enum):
    OK = "OK"
    WARNING = "WARNING"
    TRAP = "TRAP"

# ============================================
# DATA STRUCTURES
# ============================================

@dataclass
class TeamStats:
    team_name: str
    attack: float = 1.0
    defense: float = 1.0
    form: float = 1.0
    injury: float = 1.0

@dataclass
class MarketOdds:
    home: float
    draw: float
    away: float

@dataclass
class Match:
    home: str
    away: str
    league: str
    odds: MarketOdds
    home_stats: TeamStats
    away_stats: TeamStats
    kickoff: datetime

# ============================================
# UTIL: VIG REMOVAL (FIXED)
# ============================================

class OddsUtil:
    @staticmethod
    def clean_probs(odds: MarketOdds) -> Dict[str, float]:
        raw = {
            "home": 1 / odds.home,
            "draw": 1 / odds.draw,
            "away": 1 / odds.away,
        }
        s = sum(raw.values())
        return {k: v / s for k, v in raw.items()}

# ============================================
# POISSON MODEL (STABLE)
# ============================================

class PoissonModel:
    def __init__(self, base_goals=2.7):
        self.base = base_goals

    def lambda_team(self, team: TeamStats, opp: TeamStats, home: bool):
        home_boost = 1.12 if home else 1.0

        lam = (
            team.attack *
            opp.defense *
            team.form *
            team.injury *
            self.base / 2
        )

        # clamp early (important fix)
        return np.clip(lam * home_boost, 0.3, 4.5)

    def simulate_matrix(self, lh, la):
        # FAST vectorized version (FIX)
        h = np.random.poisson(lh, 8000)
        a = np.random.poisson(la, 8000)

        return {
            "home": np.mean(h > a),
            "draw": np.mean(h == a),
            "away": np.mean(h < a),
            "hg": np.mean(h),
            "ag": np.mean(a),
            "std": (np.std(h) + np.std(a)) / 2
        }

# ============================================
# TRAP DETECTOR (SIMPLIFIED + STABLE)
# ============================================

class TrapDetector:
    def detect(self, model, market):
        diff = abs(model["home"] - market["home"])

        if diff < 0.08:
            return TrapSignal.OK, diff
        elif diff < 0.15:
            return TrapSignal.WARNING, diff
        else:
            return TrapSignal.TRAP, diff

# ============================================
# KELLY (SAFE)
# ============================================

class Kelly:
    @staticmethod
    def stake(prob, odds):
        if odds <= 1:
            return 0
        b = odds - 1
        k = (b * prob - (1 - prob)) / b
        return max(0, min(k, 0.05))

# ============================================
# ENGINE (OPTIMIZED)
# ============================================

class Engine:
    def __init__(self):
        self.model = PoissonModel()
        self.trap = TrapDetector()

    def analyze(self, match: Match):

        market = OddsUtil.clean_probs(match.odds)

        lh = self.model.lambda_team(match.home_stats, match.away_stats, True)
        la = self.model.lambda_team(match.away_stats, match.home_stats, False)

        sim = self.model.simulate_matrix(lh, la)

        trap_sig, trap_score = self.trap.detect(sim, market)

        ev_home = sim["home"] * match.odds.home - 1

        return {
            "probs": sim,
            "lambda": (lh, la),
            "trap": trap_sig,
            "trap_score": trap_score,
            "ev_home": ev_home,
            "kelly_home": Kelly.stake(sim["home"], match.odds.home)
        }

# ============================================
# STREAMLIT (NON-BLOCKING FIX)
# ============================================

class App:
    def __init__(self):
        self.engine = Engine()

    def run(self):
        st.title("⚽ Trading System v2 (Upgraded)")

        matches = self.demo()

        results = []
        for m in matches:
            results.append(self.engine.analyze(m))

        df = pd.DataFrame([
            {
                "Match": f"{m.home} vs {m.away}",
                "Home Prob": r["probs"]["home"],
                "Away Prob": r["probs"]["away"],
                "EV": r["ev_home"],
                "Trap": r["trap"].value,
                "Kelly": r["kelly_home"]
            }
            for m, r in zip(matches, results)
        ])

        st.dataframe(df)

    def demo(self):
        return [
            Match(
                home="Man City",
                away="Arsenal",
                league="EPL",
                odds=MarketOdds(1.8, 3.6, 4.2),
                home_stats=TeamStats("City", 1.3, 0.9, 1.2, 1.0),
                away_stats=TeamStats("Arsenal", 1.1, 1.0, 1.1, 1.0),
                kickoff=datetime.now()
            )
        ]

# ============================================
# MAIN
# ============================================

if __name__ == "__main__":
    App().run()
