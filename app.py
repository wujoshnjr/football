import numpy as np
import asyncio
from dataclasses import dataclass
from enum import Enum
from scipy import stats


# =========================
# ENUM
# =========================

class TrapSignal(Enum):
    OK = "OK"
    WARNING = "WARNING"
    TRAP = "TRAP"


# =========================
# DATA MODEL
# =========================

@dataclass
class TeamStats:
    attack: float = 1.0
    defense: float = 1.0
    form: float = 1.0
    fatigue: float = 1.0
    lineup_strength: float = 1.0


@dataclass
class MatchData:
    home_team: str
    away_team: str
    league: str
    home_stats: TeamStats
    away_stats: TeamStats
    odds_home: float
    odds_draw: float
    odds_away: float


@dataclass
class ModelOutput:
    home_prob: float
    draw_prob: float
    away_prob: float
    xg_home: float
    xg_away: float
    trap_signal: str


# =========================
# CORE ENGINE
# =========================

class FootballTradingEngine:

    def __init__(self):
        self.league_avg = 2.7

    # -------------------------
    # FEATURE ENGINEERING
    # -------------------------
    def compute_xg(self, home: TeamStats, away: TeamStats):
        home_xg = (
            home.attack *
            away.defense *
            home.form *
            home.lineup_strength *
            (1 / home.fatigue)
        ) * self.league_avg / 2

        away_xg = (
            away.attack *
            home.defense *
            away.form *
            away.lineup_strength *
            (1 / away.fatigue)
        ) * self.league_avg / 2

        return home_xg, away_xg

    # -------------------------
    # MONTE CARLO SIMULATION
    # -------------------------
    def simulate(self, xg_h, xg_a, n=20000):

        h = np.random.poisson(xg_h, n)
        a = np.random.poisson(xg_a, n)

        home = np.mean(h > a)
        draw = np.mean(h == a)
        away = np.mean(h < a)

        return home, draw, away

    # -------------------------
    # TRAP DETECTOR (IMPROVED)
    # -------------------------
    def detect_trap(self, model, odds):

        mh, md, ma = model
        oh = 1 / odds["home"]
        od = 1 / odds["draw"]
        oa = 1 / odds["away"]

        diff = abs(mh - oh)

        if diff > 0.20:
            return "TRAP"
        elif diff > 0.12:
            return "WARNING"
        return "OK"

    # -------------------------
    # MAIN PIPELINE
    # -------------------------
    async def analyze_match(self, match: MatchData):

        xg_h, xg_a = self.compute_xg(
            match.home_stats,
            match.away_stats
        )

        home, draw, away = self.simulate(xg_h, xg_a)

        trap = self.detect_trap(
            (home, draw, away),
            {
                "home": match.odds_home,
                "draw": match.odds_draw,
                "away": match.odds_away
            }
        )

        return ModelOutput(
            home_prob=home,
            draw_prob=draw,
            away_prob=away,
            xg_home=xg_h,
            xg_away=xg_a,
            trap_signal=trap
        )

    # -------------------------
    # DEMO DATA
    # -------------------------
    async def fetch_live_data(self, leagues):

        return [
            MatchData(
                home_team="Team A",
                away_team="Team B",
                league="EPL",
                home_stats=TeamStats(1.2, 0.9, 1.1, 1.0, 1.0),
                away_stats=TeamStats(1.0, 1.1, 0.9, 1.2, 1.0),
                odds_home=1.9,
                odds_draw=3.2,
                odds_away=4.0
            )
        ]
