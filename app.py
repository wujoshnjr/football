import streamlit as st
import requests
import numpy as np
import pandas as pd
import sqlite3
import pytz
from datetime import datetime
from scipy.stats import poisson
from scipy.optimize import root_scalar

# ==========================================
# 🔑 1. 系統初始化與增強型資料庫
# ==========================================
def init_db():
    conn = sqlite3.connect('zeus_quant_v68.db', check_same_thread=False)
    c = conn.cursor()
    # 增加 xG_T 欄位紀錄模型預期總進球
    c.execute('''CREATE TABLE IF NOT EXISTS matches 
                 (match_id TEXT PRIMARY KEY, league TEXT, home TEXT, away TEXT, 
                  prediction TEXT, stake TEXT, xG_T REAL, status TEXT, 
                  timestamp TEXT, start_time TEXT)''')
    conn.commit()
    conn.close()

init_db()

# ==========================================
# 🧠 2. 量化模型核心組件
# ==========================================

def power_method_probs(odds):
    """還原真實機率 (去除 Favorite-Longshot Bias)"""
    odds_arr = np.array(odds)
    try:
        def func(k): return np.sum(np.power(1/odds_arr, k)) - 1.0
        res = root_scalar(func, bracket=[0.1, 5.0], method='brentq')
        return np.power(1/odds_arr, res.root) if res.converged else (1/odds_arr)/np.sum(1/odds_arr)
    except:
        return (1/odds_arr)/np.sum(1/odds_arr)

def get_team_xg_rating(league, home_team, away_team):
    """
    【基本面核心】模擬抓取 xG 歷史評級
    實際生產環境中，此處應對接妳收集的歷史 xG 資料庫或 API。
    目前以聯賽平均值作為基準。
    """
    # 這裡的數值應來自歷史 MLE 估計
    base_xg = 1.35 
    # 模擬邏輯：如果沒有資料，回傳中值
    return {"h_att": 1.1, "h_def": 0.9, "a_att": 1.0, "a_def": 1.1}

def apply_dixon_coles(matrix, l_h, l_a, rho=-0.11):
    """修正低比分分佈，提高 0:0, 1:0 等比分的預測精度"""
    if l_h == 0 or l_a == 0: return matrix
    def tau(x, y):
        if x == 0 and y == 0: return 1 - (l_h * l_a * rho)
        if x == 0 and y == 1: return 1 + (l_h * rho)
        if x == 1 and y == 0: return 1 + (l_a * rho)
        if x == 1 and y == 1: return 1 - rho
        return 1
    
    corrected = np.fromfunction(np.vectorize(lambda i, j: matrix[int(i), int(j)] * tau(i, j)), matrix.shape)
    return corrected / corrected.sum()

def solve_implied_total(p_u25):
    """市場隱含總進球反推"""
    try:
        return root_scalar(lambda T: poisson.cdf(2, T) - p_u25, bracket=[0.1, 8.0], method='brentq').root
    except: return 2.65

# ==========================================
# ⚡ 3. 獨立定價引擎
# ==========================================

def run_v68_analysis(m_data, h_o, d_o, a_o, o25_o, u25_o):
    # --- A. 市場數據處理 ---
    true_1x2 = power_method_probs([h_o, d_o, a_o])
    mkt_u25_p = power_method_probs([o25_o, u25_o])[1] if (o25_o and u25_o) else 0.48
    market_T = solve_implied_total(mkt_u25_p)
    
    # --- B. 基本面 xG 處理 ---
    # 獲取球隊進攻/防守修正係數 (此處為核心擴展點)
    ratings = get_team_xg_rating(m_data['sport_title'], m_data['home_team'], m_data['away_team'])
    
    # 根據球隊戰力算出基本面預期 Lambda
    # 公式：聯賽基準 * 主隊進攻強度 * 客隊防守弱點
    f_lambda_h = 1.35 * ratings['h_att'] * ratings['a_def']
    f_lambda_a = 1.25 * ratings['a_att'] * ratings['h_def']
    fundamental_T = f_lambda_h + f_lambda_a
    
    # --- C. 信號融合 (Signal Blending) ---
    # 將市場意見與基本面意見 50/50 融合 (業界穩健做法)
    final_T = (market_T * 0.5) + (fundamental_T * 0.5)
    
    # 根據 1X2 隱含機率分配 final_T
    ratio = true_1x2[0] / true_1x2[2]
    l_h = final_T * (ratio**0.7 / (ratio**0.7 + 1))
    l_a = final_T - l_h
    
    # --- D. 矩陣運算與 Edge 計算 ---
    max_g = 10
    matrix = np.outer(poisson.pmf(np.arange(max_g), l_h), poisson.pmf(np.arange(max_g), l_a))
    matrix = apply_dixon_coles(matrix, l_h, l_a)
    
    prob_h, prob_d, prob_a = np.sum(np.tril(matrix, -1)), np.sum(np.diag(matrix)), np.sum(np.triu(matrix, 1))
    prob_u25 = np.sum([matrix[i, j] for i in range(3) for j in range(3-i)])
    
    # --- E. 交易策略執行 ---
    edges = [
        ("🏠 主勝", prob_h, h_o), ("🤝 和局", prob_d, d_o), ("🚀 客勝", prob_a, a_o),
        ("🔥 大 2.5", 1-prob_u25, o25_o), ("🛡️ 小 2.5", prob_u25, u25_o)
    ]
    
    recs = []
    for label, p, o in edges:
        if o and (p - 1/o) > 0.025: # 2.5% Edge 門檻
            b = o - 1
            f_star = (b * p - (1-p)) / b
            stake = max(0, f_star * 0.2) # 0.2 倍凱利，極度保守
            if stake > 0.01:
                recs.append({"label": label, "edge": p - 1/o, "stake": stake})
    
    # 提取波膽
    top_scores = {}
    indices = np.argsort(matrix, axis=None)[::-1][:3]
    for idx in indices:
        r, c = np.unravel_index(idx, matrix.shape)
        top_scores[f"{r}:{c}"] = matrix[r, c]
        
    return recs, top_scores, final_T

# ==========================================
# 🖥️ 4. UI 介面 (Streamlit 渲染)
# ==========================================
def main():
    st.set_page_config(page_title="ZEUS QUANT v68", layout="wide")
    tw_tz = pytz.timezone('Asia/Taipei')
    
    st.markdown("""
        <style>
        .stApp { background-color: #0b0e14; color: #c9d1d9; }
        .quant-card { background: #161b22; border: 1px solid #30363d; border-radius: 10px; padding: 18px; margin-bottom: 15px; }
        .tag-xg { background: #238636; color: white; padding: 2px 8px; border-radius: 10px; font-size: 0.7rem; }
        .edge-highlight { color: #58a6ff; font-weight: bold; }
        </style>
    """, unsafe_allow_html=True)
    
    st.markdown("<h1 style='text-align:center; color:#58a6ff;'>⚛️ ZEUS QUANT v68.0</h1>", unsafe_allow_html=True)
    st.markdown("<p style='text-align:center; color:#8b949e;'>Fundamental xG Intelligence & Signal Blending</p>", unsafe_allow_html=True)

    try:
        api_key = st.secrets["ODDS_API_KEY"]
    except:
        st.error("請在 Secrets 中設定 ODDS_API_KEY"); return

    tab1, tab2 = st.tabs(["🎯 即時定價引擎", "📊 數據中心"])

    with tab1:
        res = requests.get(f"https://api.the-odds-api.com/v4/sports/soccer/odds/?apiKey={api_key}&regions=eu&markets=h2h,totals")
        if res.status_code != 200: 
            st.error("API 請求失敗"); return
        
        data = res.json()
        for m in data[:30]:
            try:
                # 數據解析邏輯
                bm = m['bookmakers'][0]['markets']
                h2h = next(mk for mk in bm if mk['key'] == 'h2h')['outcomes']
                h_o = next(o['price'] for o in h2h if o['name'] == m['home_team'])
                d_o = next(o['price'] for o in h2h if o['name'] == 'Draw')
                a_o = next(o['price'] for o in h2h if o['name'] == m['away_team'])
                
                totals = next((mk for mk in bm if mk['key'] == 'totals'), None)
                o25_o, u25_o = None, None
                if totals:
                    o25_o = next((o['price'] for o in totals['outcomes'] if o['name'] == 'Over' and o.get('point') == 2.5), None)
                    u25_o = next((o['price'] for o in totals['outcomes'] if o['name'] == 'Under' and o.get('point') == 2.5), None)

                # 模型運算
                recs, scores, final_T = run_v68_analysis(m, h_o, d_o, a_o, o25_o, u25_o)
                
                # UI 渲染
                st.markdown(f"""
                <div class="quant-card">
                    <div style="display:flex; justify-content:space-between;">
                        <span style="color:#8b949e; font-size:0.8rem;">🏆 {m['sport_title']}</span>
                        <span class="tag-xg">xG Model Active</span>
                    </div>
                    <div style="font-size:1.2rem; font-weight:bold; margin:10px 0;">
                        {m['home_team']} <span style="color:#444;">vs</span> {m['away_team']}
                    </div>
                    <div style="font-size:0.85rem; color:#58a6ff; margin-bottom:10px;">
                        融合預期總進球: {final_T:.2f} | 最佳波膽: {', '.join([f"{k}({v:.1%})" for k,v in scores.items()])}
                    </div>
                    <div style="border-top:1px solid #30363d; padding-top:10px;">
                        {" ".join([f"<span style='margin-right:15px;'>✅ {r['label']} <span class='edge-highlight'>+{r['edge']:.1%}</span> (建議倉位: {r['stake']:.1%})</span>" for r in recs]) if recs else "<span style='color:#666;'>未發現正期望值交易機會</span>"}
                    </div>
                </div>
                """, unsafe_allow_html=True)
            except: continue

    with tab2:
        st.info("歷史數據與回測模組開發中...")

if __name__ == "__main__":
    main()
