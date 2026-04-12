# ============================================
# 🏦 FOOTBALL TRADING SYSTEM v3 (FULL INTEGRATED)
# ============================================

import numpy as np
import pandas as pd
import streamlit as st
from scipy import stats

# ============================================
# CONFIG
# ============================================

st.set_page_config(layout="wide")
st.title("🏦 Institutional Football Trading Desk v3")

# ============================================
# CORE MODELS
# ============================================

class PoissonModel:

    def __init__(self, league_avg=2.75):
        self.league_avg = league_avg

    def xg(self, attack, defense):
        return attack * defense * self.league_avg / 2

    def score_matrix(self, hxg, axg, max_goals=6):

        out = {}

        for h in range(max_goals):
            for a in range(max_goals):

                p = stats.poisson.pmf(h, hxg) * stats.poisson.pmf(a, axg)
                out[f"{h}-{a}"] = p

        return out


class MonteCarlo:

    def __init__(self, n=100000):
        self.n = n

    def simulate(self, hxg, axg):

        h = np.random.poisson(hxg, self.n)
        a = np.random.poisson(axg, self.n)

        return {
            "home": np.mean(h > a),
            "draw": np.mean(h == a),
            "away": np.mean(h < a),
            "over25": np.mean(h + a > 2.5),
            "over35": np.mean(h + a > 3.5),
            "h_mean": np.mean(h),
            "a_mean": np.mean(a),
            "h_std": np.std(h),
            "a_std": np.std(a),
        }


class Kelly:

    def calc(self, p, odds, frac=0.25):

        if odds <= 1:
            return 0

        b = odds - 1
        q = 1 - p

        k = (b * p - q) / b

        return max(0, k * frac)


class TrapDetector:

    def detect(self, model_p, market_p):

        diff = abs(model_p - market_p)

        if diff < 0.1:
            return "OK"
        elif diff < 0.2:
            return "WARNING"
        else:
            return "TRAP"


# ============================================
# ENGINE
# ============================================

class Engine:

    def __init__(self):

        self.p = PoissonModel()
        self.mc = MonteCarlo()
        self.kelly = Kelly()
        self.trap = TrapDetector()

    def run(self, m):

        # =========================
        # xG
        # =========================

        hxg = self.p.xg(m["ha"], m["ad"])
        axg = self.p.xg(m["aa"], m["hd"])

        # =========================
        # SIMULATION
        # =========================

        sim = self.mc.simulate(hxg, axg)

        # =========================
        # SCORELINE
        # =========================

        scores = self.p.score_matrix(hxg, axg)
        top5 = sorted(scores.items(), key=lambda x: x[1], reverse=True)[:5]

        # =========================
        # EV
        # =========================

        ev = {
            "home": sim["home"] * m["oh"] - 1,
            "draw": sim["draw"] * m["od"] - 1,
            "away": sim["away"] * m["oa"] - 1,
        }

        # =========================
        # KELLY
        # =========================

        kelly = {
            "home": self.kelly.calc(sim["home"], m["oh"]),
            "draw": self.kelly.calc(sim["draw"], m["od"]),
            "away": self.kelly.calc(sim["away"], m["oa"]),
        }

        # =========================
        # TRAP
        # =========================

        trap = self.trap.detect(sim["home"], 0.5)

        # =========================
        # OUTPUT
        # =========================

        return {
            "xg_h": hxg,
            "xg_a": axg,

            "home": sim["home"],
            "draw": sim["draw"],
            "away": sim["away"],

            "over25": sim["over25"],
            "over35": sim["over35"],

            "score": top5,

            "ev": ev,
            "kelly": kelly,
            "trap": trap,

            "std": (sim["h_std"] + sim["a_std"]) / 2
        }


# ============================================
# UI ENGINE
# ============================================

engine = Engine()

match = {
    "ha": 1.25,   # home attack
    "hd": 0.95,   # home defense
    "aa": 1.10,   # away attack
    "ad": 1.00,   # away defense

    "oh": 1.85,
    "od": 3.60,
    "oa": 4.20
}

result = engine.run(match)

# ============================================
# DASHBOARD
# ============================================

col1, col2, col3 = st.columns(3)

with col1:
    st.metric("Home", f"{result['home']:.2%}")
    st.metric("Draw", f"{result['draw']:.2%}")
    st.metric("Away", f"{result['away']:.2%}")

with col2:
    st.metric("xG Home", f"{result['xg_h']:.2f}")
    st.metric("xG Away", f"{result['xg_a']:.2f}")

with col3:
    st.metric("Over 2.5", f"{result['over25']:.2%}")
    st.metric("Over 3.5", f"{result['over35']:.2%}")

st.markdown("---")

st.subheader("📊 Top Scorelines")

for s, p in result["score"]:
    st.write(s, f"{p:.2%}")

st.markdown("---")

st.subheader("💰 EV")

st.write(result["ev"])

st.subheader("📈 Kelly")

st.write(result["kelly"])

st.subheader("🚨 Trap Signal")

st.write(result["trap"])
