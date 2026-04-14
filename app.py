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
# 🔑 1. 初始化量化數據庫
# ==========================================
def init_db():
    conn = sqlite3.connect('zeus_master_v70.db', check_same_thread=False)
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS matches 
                 (match_id TEXT PRIMARY KEY, league TEXT, home TEXT, away TEXT, 
                  prediction TEXT, timestamp TEXT)''')
    conn.commit()
    conn.close()

init_db()

# ==========================================
# 🧠 2. 量化運算引擎 (Power Method + Dixon-Coles)
# ==========================================

def power_method_probs(odds):
    """還原莊家抽水後的真實機率"""
    odds_arr = np.array(odds)
    try:
        def func(k): return np.sum(np.power(1/odds_arr, k)) - 1.0
        res = root_scalar(func, bracket=[0.1, 5.0], method='brentq')
        if res.converged:
            return np.power(1/odds_arr, res.root)
        return (1/odds_arr) / np.sum(1/odds_arr)
    except:
        return (1/odds_arr) / np.sum(1/odds_arr)

def apply_dixon_coles(matrix, l_h, l_a, rho=-0.1):
    """修正低比分偏差，提升平局預測精度"""
    def tau(x, y, lh, la, r):
        if x == 0 and y == 0: return 1 - lh * la * r
        if x == 0 and y == 1: return 1 + lh * r
        if x == 1 and y == 0: return 1 + la * r
        if x == 1 and y == 1: return 1 - r
        return 1
    corrected = matrix.copy()
    for i in range(2):
        for j in range(2):
            corrected[i, j] *= tau(i, j, l_h, l_a, rho)
    return corrected / corrected.sum()

def solve_implied_total(p_u25):
    """從大小球賠率反推預期總進球數 T"""
    def obj(T): return poisson.cdf(2, T) - p_u25
    try:
        return root_scalar(obj, bracket=[0.1, 8.0], method='brentq').root
    except: return 2.65

def calculate_kelly(my_prob, bookie_odds, fraction=0.2):
    """1/5 凱利準則資金管理"""
    if not bookie_odds or bookie_odds <= 1: return 0
    b = bookie_odds - 1
    f_star = (b * my_prob - (1 - my_prob)) / b
    return max(0, f_star * fraction)

# ==========================================
# ⚡ 3. 核心量化路徑：強制輸出預測
# ==========================================

def run_quant_analysis(h_o, d_o, a_o, o25_o, u25_o):
    # 1. 去水還原真實機率
    p_h, p_d, p_a = power_method_probs([h_o, d_o, a_o])
    p_u25 = power_method_probs([o25_o, u25_o])[1] if (o25_o and u25_o) else 0.48
    
    # 2. 反推數據期望值
    T = solve_implied_total(p_u25)
    ratio = p_h / p_a
    l_h = T * (ratio**0.72 / (ratio**0.72 + 1))
    l_a = T - l_h
    
    # 3. 矩陣運算 (6x6 精度)
    pmf_h = poisson.pmf(np.arange(6), l_h)
    pmf_a = poisson.pmf(np.arange(6), l_a)
    matrix = apply_dixon_coles(np.outer(pmf_h, pmf_a), l_h, l_a)
    
    # 4. 計算模型指標
    m_h = np.sum(np.tril(matrix, -1))
    m_d = np.sum(np.diag(matrix))
    m_a = np.sum(np.triu(matrix, 1))
    m_u25 = np.sum([matrix[i, j] for i in range(3) for j in range(3-i)])
    m_o25 = 1 - m_u25
    
    # 5. 強制判定邏輯
    targets = [
        ("🏠 主勝", m_h, h_o), ("🤝 和局", m_d, d_o), ("🚀 客勝", m_a, a_o),
        ("🔥 大 2.5", m_o25, o25_o), ("🛡️ 小 2.5", m_u25, u25_o)
    ]
    
    recs = []
    for label, prob, odds in targets:
        if odds:
            edge = prob - (1/odds)
            if edge > 0.025:
                recs.append({"label": label, "edge": edge, "stake": calculate_kelly(prob, odds), "tag": "🎯 實戰建議"})
            elif edge > 0:
                recs.append({"label": label, "edge": edge, "stake": 0.01, "tag": "📊 數據傾向"})
    
    # 如果完全沒優勢，抓機率最高項 (不再數據觀望)
    if not recs:
        idx = np.argmax([m_h, m_d, m_a])
        labels = ["🏠 主勝", "🤝 和局", "🚀 客勝"]
        recs.append({"label": labels[idx], "edge": 0.0, "stake": 0.005, "tag": "⚠️ 盤口平衡"})
    
    # 提取波膽
    scores = {}
    top_indices = np.argsort(matrix, axis=None)[::-1][:3]
    for i in top_indices:
        r, c = np.unravel_index(i, matrix.shape)
        scores[f"{r}:{c}"] = matrix[r, c]
        
    return recs, scores, T

# ==========================================
# 🖥️ 4. Streamlit UI 穩定渲染
# ==========================================

def main():
    st.set_page_config(page_title="ZEUS QUANT MASTER", layout="wide")
    tw_tz = pytz.timezone('Asia/Taipei')
    
    st.markdown("""
    <style>
        .stApp { background-color: #0d1117; color: #e6edf3; }
        .match-card { background: #161b22; border: 1px solid #30363d; border-radius: 12px; padding: 20px; margin-bottom: 20px; border-left: 5px solid #8a2be2; }
        .team-title { font-size: 1.4rem; font-weight: 800; color: #ffffff; }
    </style>
    """, unsafe_allow_html=True)

    st.markdown("<h1 style='text-align:center; color:#8a2be2;'>⚛️ ZEUS QUANT v70.0</h1>", unsafe_allow_html=True)

    try: 
        api_key = st.secrets["ODDS_API_KEY"]
    except: 
        st.error("❌ 未在 Secrets 中設定 ODDS_API_KEY"); return

    tab1, tab2 = st.tabs(["🎯 量化預測中心", "📊 數據歷史"])

    with tab1:
        url = f"https://api.the-odds-api.com/v4/sports/soccer/odds/?apiKey={api_key}&regions=eu&markets=h2h,totals"
        res = requests.get(url)
        if res.status_code != 200: st.error("API 請求額度已滿或連線問題"); return
        
        data = res.json()
        st.write(f"最後同步: {datetime.now(tw_tz).strftime('%Y-%m-%d %H:%M:%S')}")

        for m in data[:25]:
            try:
                bm = m['bookmakers'][0]['markets']
                h2h = next(mk for mk in bm if mk['key'] == 'h2h')
                totals = next((mk for mk in bm if mk['key'] == 'totals'), None)
                
                h_o = next(o['price'] for o in h2h['outcomes'] if o['name'] == m['home_team'])
                d_o = next(o['price'] for o in h2h['outcomes'] if o['name'] == 'Draw')
                a_o = next(o['price'] for o in h2h['outcomes'] if o['name'] == m['away_team'])
                
                o25_o = next((o['price'] for o in totals['outcomes'] if o['name'] == 'Over' and o.get('point') == 2.5), 2.0) if totals else 2.0
                u25_o = next((o['price'] for o in totals['outcomes'] if o['name'] == 'Under' and o.get('point') == 2.5), 2.0) if totals else 2.0

                # 核心分析
                recs, scores, T = run_quant_analysis(h_o, d_o, a_o, o25_o, u25_o)
                start_time = datetime.strptime(m['commence_time'], "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=pytz.utc).astimezone(tw_tz)

                # 使用 st 組件取代 HTML 避免渲染錯誤
                with st.container():
                    st.markdown(f"""<div class="match-card">
                        <div style="font-size:0.8rem; color:#8b949e;">🏆 {m['sport_title']} | 🕒 {start_time.strftime('%m/%d %H:%M')}</div>
                        <div class="team-title">{m['home_team']} VS {m['away_team']}</div>
                        <div style="margin-top:8px;">🎯 預期總進球: {T:.2f}</div>
                    </div>""", unsafe_allow_html=True)
                    
                    # 顯示波膽
                    cols = st.columns(3)
                    for i, (score, prob) in enumerate(scores.items()):
                        cols[i].metric(f"波膽 {score}", f"{prob:.1%}")
                    
                    # 顯示建議
                    for r in recs:
                        if "實戰" in r['tag']:
                            st.success(f"**{r['tag']}** : {r['label']} (優勢: {r['edge']:+.1%} | 倉位: {r['stake']:.1%})")
                        elif "數據" in r['tag']:
                            st.info(f"**{r['tag']}** : {r['label']} (優勢: {r['edge']:+.1%} | 倉位: {r['stake']:.1%})")
                        else:
                            st.warning(f"**{r['tag']}** : {r['label']} (機率最高項)")
                    st.markdown("---")
            except: continue

    with tab2:
        st.write("SQLite 歷史數據加載中...")

if __name__ == "__main__":
    main()
