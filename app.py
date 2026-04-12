import streamlit as st
import asyncio
import numpy as np
import pandas as pd
import os
from datetime import datetime, timedelta
from dataclasses import dataclass

# =========================
# STREAMLIT FIX (CRITICAL)
# =========================

def run_async(coro):
    """Safe asyncio runner for Streamlit"""
    try:
        loop = asyncio.get_event_loop()
    except:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
    return loop.run_until_complete(coro)

# =========================
# CONFIG (你的「不可刪除規則」)
# =========================

SYSTEM_SPEC = {
    "MUST_KEEP_MODELS": [
        "PoissonModel",
        "MonteCarloSimulator",
        "AsianHandicapModel",
        "TrapDetector",
        "UpsetDetector",
        "KellyCriterion"
    ],
    "MUST_HAVE_FEATURES": [
        "Score Prediction",
        "Over/Under",
        "Asian Handicap",
        "EV Value Betting",
        "Kelly Criterion",
        "Trap Detection",
        "Upset Probability"
    ]
}

# =========================
# SIMPLE SAFE ENGINE WRAPPER
# =========================

class SafeEngineWrapper:
    def __init__(self, engine):
        self.engine = engine

    async def analyze(self, match):
        return await self.engine.analyze_match(match)

# =========================
# STREAMLIT UI (PRO STYLE)
# =========================

class ProDashboard:

    def __init__(self, engine):
        self.engine = engine
        st.set_page_config(
            page_title="Football Trading Pro",
            layout="wide"
        )

    def render_header(self):
        st.title("⚽ Professional Football Prediction Desk")
        st.caption("Institutional-grade model: Poisson + Monte Carlo + Market EV")

    def render_sidebar(self):
        st.sidebar.header("Controls")

        self.min_ev = st.sidebar.slider("Min EV", 0.0, 0.2, 0.05)
        self.kelly = st.sidebar.slider("Kelly fraction", 0.05, 0.5, 0.25)

        self.show_trap = st.sidebar.checkbox("Show trap signals", True)
        self.show_value = st.sidebar.checkbox("Only value bets", True)

    def render_match_card(self, match, result):

        col1, col2, col3 = st.columns([3, 1, 1])

        with col1:
            st.subheader(f"{match.home_team} vs {match.away_team}")
            st.write(match.league)

        with col2:
            st.metric("Home Prob", f"{result.home_prob:.2%}")
            st.metric("Away Prob", f"{result.away_prob:.2%}")

        with col3:
            st.metric("Confidence", f"{result.confidence_score:.2%}")
            st.metric("Upset", f"{result.upset_probability:.2%}")

        st.markdown("---")

    def run(self):

        self.render_header()
        self.render_sidebar()

        st.info("Loading matches...")

        matches = self.engine._generate_demo_matches()

        results = []

        for m in matches:
            result = run_async(self.engine.analyze_match(m))
            results.append((m, result))

        for match, result in results:

            ev = max(result.ev_1x2.values())

            if self.show_value and ev < self.min_ev:
                continue

            self.render_match_card(match, result)

# =========================
# ENTRY POINT FIXED
# =========================

def main():
    from your_engine import FootballTradingEngine  # 🔧 你原本 engine

    engine = FootballTradingEngine()

    dashboard = ProDashboard(engine)
    dashboard.run()

if __name__ == "__main__":
    main()
