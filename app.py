# ============================================
# FOOTBALL HEDGE FUND V6 (STABLE + FIXED)
# ============================================

import numpy as np
import pandas as pd
import streamlit as st
from datetime import datetime, timedelta
import pytz
from scipy import stats
from dataclasses import dataclass
from enum import Enum

# ============================================
# CONFIG
# ============================================

TZ = pytz.timezone("Asia/Taipei")

st.set_page_config(
    page_title="Football Hedge Fund V6",
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
    home_adv: float = 1.28   # FIXED (was too low)

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
# LEAGUE CALIBRATION (IMPORTANT FIX)
# ============================================

LEAGUE_BASE = {
    "EPL": 2.65,
    "La Liga": 2.45,
    "Serie A": 2.35,
    "Bundesliga": 3.05,
    "Ligue 1": 2.55,
    "MLS": 2.85
}

# ============================================
# POISSON ENGINE (FIXED OVER-INFLATION BUG)
# ============================================

class PoissonEngine:

    def lambda_goals(self, atk, dfn, league_avg, home_adv=1.0):
        raw = (atk / max(dfn, 0.6)) * league_avg * 0.85

        # 🔥 HARD CAP (fix over 2.5 explosion)
        return float(np.clip(raw * home_adv, 0.25, 2.8))

    def score_matrix(self, lh, la):
        max_g = 6
        out = {}

        for h in range(max_g):
            for a in range(max_g):
                p = stats.poisson.pmf(h, lh) * stats.poisson.pmf(a, la)
                out[f"{h}-{a}"] = p

        return out

# ============================================
# MONTE CARLO (CLEAN VERSION)
# ============================================

class MonteCarlo:

    def run(self, lh, la, n=100000):

        home = np.random.poisson(lh, n)
        away = np.random.poisson(la, n)

        total = home + away

        return {
            "home": np.mean(home > away),
            "draw": np.mean(home == away),
            "away": np.mean(home < away),

            "hg": np.mean(home),
            "ag": np.mean(away),

            # FIXED OVER MODEL (no bias)
            "over15": np.mean(total >= 2),
            "over25": np.mean(total >= 3),
            "over35": np.mean(total >= 4),

            "std": np.std(total)
        }

# ============================================
# KELLY
# ============================================

class Kelly:

    def stake(self, prob, odds):
        if odds <= 1:
            return 0

        b = odds - 1
        k = (b * prob - (1 - prob)) / b

        return float(np.clip(k, 0, 0.05))

# ============================================
# TRAP DETECTOR
# ============================================

def detect_trap(model_prob, market_prob):

    diff = abs(model_prob["home"] - market_prob["home"])

    if diff > 0.15:
        return TrapSignal.WARNING, diff

    return TrapSignal.OK, diff

# ============================================
# DEMO MATCHES (EXPANDED FIX)
# ============================================

def load_matches():

    base = datetime.now(TZ)

    fixtures = [
        ("Man City", "Arsenal", "EPL"),
        ("Liverpool", "Chelsea", "EPL"),
        ("Real Madrid", "Barcelona", "La Liga"),
        ("Atletico", "Sevilla", "La Liga"),
        ("Bayern", "Dortmund", "Bundesliga"),
        ("PSG", "Marseille", "Ligue 1"),
        ("Inter", "Juventus", "Serie A"),
        ("AC Milan", "Napoli", "Serie A"),
        ("Ajax", "PSV", "Eredivisie"),
        ("Benfica", "Porto", "Liga Portugal"),
        ("LAFC", "LA Galaxy", "MLS"),
        ("Newcastle", "Tottenham", "EPL"),
        ("Brighton", "West Ham", "EPL"),
        ("Leipzig", "Frankfurt", "Bundesliga"),
    ]

    matches = []

    for i, (h, a, l) in enumerate(fixtures * 2):  # 🔥 more matches

        match = Match(
            home=TeamStats(
                h,
                np.random.uniform(1.0, 1.25),
                np.random.uniform(0.85, 1.2),
                np.random.uniform(0.9, 1.2)
            ),
            away=TeamStats(
                a,
                np.random.uniform(1.0, 1.25),
                np.random.uniform(0.85, 1.2),
                np.random.uniform(0.9, 1.2)
            ),
            league=l,
            kickoff=base + timedelta(hours=i * 2),
            odds_home=np.random.uniform(1.6, 2.4),
            odds_draw=np.random.uniform(3.0, 3.8),
            odds_away=np.random.uniform(2.8, 4.5)
        )

        matches.append(match)

    return matches

# ============================================
# ENGINE
# ============================================

poisson = PoissonEngine()
mc = MonteCarlo()
kelly = Kelly()

def analyze(m):

    league_avg = LEAGUE_BASE.get(m.league, 2.6)

    lh = poisson.lambda_goals(
        m.home.attack,
        m.away.defense,
        league_avg,
        m.home.home_adv
    )

    la = poisson.lambda_goals(
        m.away.attack,
        m.home.defense,
        league_avg,
        1.0
    )

    sim = mc.run(lh, la)

    market = {
        "home": 1 / m.odds_home,
        "draw": 1 / m.odds_draw,
        "away": 1 / m.odds_away
    }

    trap, score = detect_trap(sim, market)

    ev = {
        "H": sim["home"] * m.odds_home - 1,
        "D": sim["draw"] * m.odds_draw - 1,
        "A": sim["away"] * m.odds_away - 1
    }

    return sim, market, trap, score, ev, lh, la

# ============================================
# UI
# ============================================

def main():

    st.title("🏦 Football Hedge Fund V6 (Stable Edition)")

    matches = load_matches()

    show_value = st.sidebar.checkbox("Only Value Bets", True)

    for m in matches:

        sim, market, trap, score, ev, lh, la = analyze(m)

        if show_value and max(ev.values()) < 0:
            continue

        # TIME FIX (IMPORTANT)
        kickoff = m.kickoff.astimezone(TZ).strftime("%Y-%m-%d %H:%M")

        st.markdown("---")

        # MATCH HEADER (FIXED DISPLAY)
        st.subheader(f"{m.home.name} vs {m.away.name}")
        st.caption(f"{m.league} | Kickoff (TPE): {kickoff}")

        # PROBABILITIES
        c1, c2, c3 = st.columns(3)

        c1.metric("Home", f"{sim['home']:.1%}")
        c2.metric("Draw", f"{sim['draw']:.1%}")
        c3.metric("Away", f"{sim['away']:.1%}")

        # OVER MODEL (FIXED)
        st.write("📊 Over/Under")
        st.write({
            "Over1.5": sim["over15"],
            "Over2.5": sim["over25"],
            "Over3.5": sim["over35"]
        })

        # xG
        st.write(f"⚽ xG Home: {lh:.2f} | Away: {la:.2f}")

        # EV
        st.write("💰 EV:")
        st.write(ev)

        # TRAP
        st.write(f"🚨 Trap: {trap.value} | score={score:.2f}")

        # SCORELINES
        scores = poisson.score_matrix(lh, la)
        top = sorted(scores.items(), key=lambda x: x[1], reverse=True)[:5]

        st.write("🎯 Top Scorelines:")
        st.write(top)

if __name__ == "__main__":
    main()
