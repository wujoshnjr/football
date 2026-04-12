# ============================================
# INSTITUTIONAL FOOTBALL TRADING SYSTEM v5.1 FIXED
# Hedge Fund Grade Betting Engine (FULL FIX)
# ============================================

import os
import numpy as np
import pandas as pd
import streamlit as st
from datetime import datetime, timedelta
import pytz
from dataclasses import dataclass
from typing import List, Tuple
from scipy.stats import poisson

# ============================================
# DATA STRUCTURES
# ============================================

@dataclass
class Team:
    name: str
    atk: float
    dfd: float

@dataclass
class Match:
    home: Team
    away: Team
    league: str
    kickoff: datetime
    odds: Tuple[float, float, float]

# ============================================
# TIME SYSTEM (FIXED - TAIPEI)
# ============================================

def to_taipei_time(dt):
    tz = pytz.timezone("Asia/Taipei")
    return dt.astimezone(tz).strftime("%Y-%m-%d %H:%M")

# ============================================
# POISSON MODEL (FIXED BIAS)
# ============================================

class PoissonModel:

    def predict(self, match):

        home_strength = match.home.atk * match.away.dfd
        away_strength = match.away.atk * match.home.dfd

        # ✅ FIXED HOME ADVANTAGE (之前錯誤核心)
        home_lambda = (home_strength * 1.25) / 1.15
        away_lambda = (away_strength * 1.05) / 1.15

        home_goals = poisson.pmf(range(6), home_lambda)
        away_goals = poisson.pmf(range(6), away_lambda)

        # Monte Carlo approximation probabilities
        home_prob = min(max(home_lambda / (home_lambda + away_lambda), 0.05), 0.85)
        away_prob = min(max(away_lambda / (home_lambda + away_lambda), 0.05), 0.85)
        draw_prob = max(0.10, 1 - home_prob - away_prob)

        return {
            "home": home_prob,
            "draw": draw_prob,
            "away": away_prob,
            "xg_home": home_lambda,
            "xg_away": away_lambda
        }

# ============================================
# MONTE CARLO (100K SIMULATION FIXED)
# ============================================

class MonteCarlo:

    def simulate(self, home_xg, away_xg, n=100000):

        home = np.random.poisson(home_xg, n)
        away = np.random.poisson(away_xg, n)

        home_win = np.mean(home > away)
        draw = np.mean(home == away)
        away_win = np.mean(home < away)

        return {
            "home": home_win,
            "draw": draw,
            "away": away_win,
            "avg_home_goals": np.mean(home),
            "avg_away_goals": np.mean(away),
        }

# ============================================
# KELLY + EV (SAFE)
# ============================================

def ev(prob, odds):
    return (prob * odds) - 1

def kelly(prob, odds):
    b = odds - 1
    if b <= 0:
        return 0
    k = ((b * prob) - (1 - prob)) / b
    return max(0, min(k, 0.05))  # cap 5%

# ============================================
# MATCH GENERATOR (40+ MATCHES FIXED)
# ============================================

def generate_matches():

    teams = [
        ("Arsenal", 1.35, 0.95),
        ("Chelsea", 1.25, 1.05),
        ("Liverpool", 1.50, 0.90),
        ("Man City", 1.65, 0.85),
        ("Real Madrid", 1.60, 0.88),
        ("Barcelona", 1.45, 0.95),
        ("Bayern", 1.70, 0.80),
        ("PSG", 1.40, 1.00),
        ("Inter", 1.30, 1.05),
        ("Juventus", 1.20, 1.10),
    ]

    matches = []
    base = datetime(2026, 1, 1, 18, 0)

    # ✅ FIX: 40+ matches
    for i in range(40):

        home = teams[np.random.randint(len(teams))]
        away = teams[np.random.randint(len(teams))]

        while away[0] == home[0]:
            away = teams[np.random.randint(len(teams))]

        kickoff = base + timedelta(hours=i * 3)

        matches.append(
            Match(
                home=Team(*home),
                away=Team(*away),
                league="EURO LEAGUE",
                kickoff=kickoff,
                odds=(
                    round(np.random.uniform(1.5, 2.5), 2),
                    round(np.random.uniform(3.0, 4.2), 2),
                    round(np.random.uniform(3.2, 5.5), 2),
                )
            )
        )

    return matches

# ============================================
# STREAMLIT UI (FIXED DISPLAY)
# ============================================

def main():

    st.set_page_config(page_title="Football Hedge Fund v5.1", layout="wide")

    st.title("🏦 Football Trading System v5.1 FIXED")
    st.markdown("### Hedge Fund Simulation Engine (Corrected)")

    model = PoissonModel()
    mc = MonteCarlo()

    matches = generate_matches()

    st.success(f"Loaded {len(matches)} matches")

    for m in matches:

        pred = model.predict(m)
        sim = mc.simulate(pred["xg_home"], pred["xg_away"])

        st.markdown("---")

        # ================= FIXED MATCH UI =================
        col1, col2, col3 = st.columns([3, 1, 1])

        with col1:
            st.subheader(f"{m.home.name} vs {m.away.name}")
            st.write(f"🏆 {m.league}")
            st.write(f"🕒 Kickoff: {to_taipei_time(m.kickoff)}")

        with col2:
            st.metric("Home Prob", f"{sim['home']:.2%}")
            st.metric("Draw Prob", f"{sim['draw']:.2%}")
            st.metric("Away Prob", f"{sim['away']:.2%}")

        with col3:
            ev_home = ev(sim["home"], m.odds[0])
            ev_draw = ev(sim["draw"], m.odds[1])
            ev_away = ev(sim["away"], m.odds[2])

            st.write("📊 EV:")
            st.write(f"H: {ev_home:.2f}")
            st.write(f"D: {ev_draw:.2f}")
            st.write(f"A: {ev_away:.2f}")

            st.write("💰 Kelly:")
            st.write(f"H: {kelly(sim['home'], m.odds[0]):.2%}")
            st.write(f"D: {kelly(sim['draw'], m.odds[1]):.2%}")
            st.write(f"A: {kelly(sim['away'], m.odds[2]):.2%}")

        st.write(f"⚽ xG: {pred['xg_home']:.2f} - {pred['xg_away']:.2f}")
        st.write(f"📈 Avg Goals: {sim['avg_home_goals']:.2f} - {sim['avg_away_goals']:.2f}")

# ============================================
# RUN
# ============================================

if __name__ == "__main__":
    main()
