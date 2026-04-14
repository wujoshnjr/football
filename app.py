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
# 🔑 1. 系統初始化與資料庫
# ==========================================
def init_db():
    conn = sqlite3.connect('zeus_quant_v69.db', check_same_thread=False)
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS matches 
                 (match_id TEXT PRIMARY KEY, league TEXT, home TEXT, away TEXT, 
                  prediction TEXT, stake TEXT, status TEXT, 
                  timestamp TEXT, start_time TEXT)''')
    conn.commit()
    conn.close()

init_db()

# ==========================================
# 🧠 2. 專業量化核心 (修正 v60 類型錯誤)
# ==========================================

def power_method_probs(odds):
    """還原真實機率，對抗 Favorite-Longshot Bias"""
    odds_arr = np.array(odds)
    try:
        def func(k): return np.sum(np.power(1/odds_arr, k)) - 1.0
        res = root_scalar(func, bracket=[0.1, 5.0], method='brentq')
        if res.converged: return np.power(1/odds_arr, res.root)
        return (1/odds_arr) / np.sum(1/odds_arr)
    except:
        return (1/odds_arr) / np.sum(1/odds_arr)

def apply_dixon_coles(matrix, l_h, l_a, rho=-0.1):
    """修正低比分偏差"""
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
    """從大小球盤口反推預期總進球數 T"""
    def obj(T): return poisson.cdf(2, T) - p_u25
    try:
        return root_scalar(obj, bracket=[0.1, 8.0], method='brentq').root
    except: return 2.65

def calculate_kelly(my_prob, bookie_odds, fraction=0.2):
    """資金管理：1/5 凱利準則"""
    if not bookie_odds or bookie_odds <= 1: return 0
    b = bookie_odds - 1
    f_star = (b * my_prob - (1 - my_prob)) / b
    return max(0, f_star * fraction)

# ==========================================
# ⚡ 3. 實戰數據干預與分析流
# ==========================================

def run_analysis_v69(h_o, d_o, a_o, o25_o, u25_o):
    # 1. 基礎去水
    p_h, p_d, p_a = power_method_probs([h_o, d_o, a_o])
    p_u25 = power_method_probs([o25_o, u25_o])[1] if (o25_o and u25_o) else 0.48
    
    # 2. 獲取預期總進球 T
    T = solve_implied_total(p_u25)
    
    # 3. 攻防 Lambda 分配 (加入數據擬合權重)
    ratio = p_h / p_a
    l_h = T * (ratio**0.72 / (ratio**0.72 + 1))
    l_a = T - l_h
    
    # 4. 生成 10x10 修正矩陣
    pmf_h = poisson.pmf(np.arange(10), l_h)
    pmf_a = poisson.pmf(np.arange(10), l_a)
    matrix = apply_dixon_coles(np.outer(pmf_h, pmf_a), l_h, l_a)
    
    # 5. 計算模型機率
    m_h, m_d, m_a = np.sum(np.tril(matrix, -1)), np.sum(np.diag(matrix)), np.sum(np.triu(matrix, 1))
    m_u25 = np.sum([matrix[i, j] for i in range(3) for j in range(3-i)])
    m_o25 = 1 - m_u25
    
    # 6. 強制判定與 Edge 分級
    targets = [
        ("🏠 主勝", m_h, h_o), ("🤝 和局", m_d, d_o), ("🚀 客勝", m_a, a_o),
        ("🔥 大 2.5", m_o25, o25_o), ("🛡️ 小 2.5", m_u25, u25_o)
    ]
    
    recs = []
    for label, prob, odds in targets:
        if odds and odds > 0:
            edge = prob - (1/odds)
            if edge > 0.025:
                recs.append({"label": label, "edge": edge, "stake": calculate_kelly(prob, odds), "tag": "🎯 實戰建議"})
            elif edge > 0:
                recs.append({"label": label, "edge": edge, "stake": 0.01, "tag": "📊 數據傾向"})

    # 若無任何正 Edge，強行給出機率最高項 (盤口平衡模式)
    if not recs:
        probs = [m_h, m_d, m_a]
        idx = np.argmax(probs)
        labels = ["🏠 主勝", "🤝 和局", "🚀 客勝"]
        odds_list = [h_o, d_o, a_o]
        recs.append({
            "label": labels[idx], 
            "edge": probs[idx] - (1/odds_list[idx]), 
            "stake": 0.005, 
            "tag": "⚠️ 盤口平衡(參考)"
        })
    
    # 波膽 Top 3
    scores = {}
    top_idx = np.argsort(matrix, axis=None)[::-1][:3]
    for i in top_idx:
        r, c = np.unravel_index(i, matrix.shape)
        scores[f"{r}:{c}"] = matrix[r, c]
        
    return recs, scores, T

# ==========================================
# 🎨 4. UI 介面與渲染
# ==========================================
def apply_styles():
    st.markdown("""
    <style>
        .stApp { background-color: #0d1117; color: #e6edf3; }
        .master-card { background: #161b22; border: 1px solid #30363d; border-radius: 12px; padding: 20px; margin-bottom: 20px; border-left: 6px solid #8a2be2; }
        .team-line { font-size: 1.4rem; font-weight: 800; color: #ffffff; margin-bottom: 12px; }
        .score-badge { background: #21262d; color: #58a6ff; padding: 4px 10px; border-radius: 5px; font-size: 0.85rem; border: 1px solid #30363d; margin-right: 8px; display: inline-block; font-family: monospace; }
        .rec-box { margin-top: 10px; padding: 10px; border-radius: 8px; background: rgba(255,255,255,0.03); border: 1px solid #444; }
    </style>
    """, unsafe_allow_html=True)

def main():
    apply_styles()
    tw_tz = pytz.timezone('Asia/Taipei')
    st.markdown("<h1 style='text-align:center; color:#8a2be2;'>⚛️ ZEUS QUANT TERMINAL v69.0</h1>", unsafe_allow_html=True)
    st.markdown("<p style='text-align:center; color:#8b949e;'>數據驅動 · 實戰干預版</p>", unsafe_allow_html=True)

    try: 
        api_key = st.secrets["ODDS_API_KEY"]
    except: 
        st.error("❌ 找不到 API Key"); return

    tab1, tab2 = st.tabs(["🎯 即時量化分析", "📚 歷史覆盤"])

    with tab1:
        url = f"https://api.the-odds-api.com/v4/sports/soccer/odds/?apiKey={api_key}&regions=eu&markets=h2h,totals"
        res = requests.get(url)
        if res.status_code != 200: st.error("API 連線失敗"); return
        
        data = res.json()
        st.write(f"最後更新: {datetime.now(tw_tz).strftime('%H:%M:%S')} | 餘額: {res.headers.get('x-requests-remaining')}")

        for m in data[:30]:
            try:
                bm = m['bookmakers'][0]['markets']
                h2h = next(mk for mk in bm if mk['key'] == 'h2h')
                totals = next((mk for mk in bm if mk['key'] == 'totals'), None)
                
                h_o = next(o['price'] for o in h2h['outcomes'] if o['name'] == m['home_team'])
                d_o = next(o['price'] for o in h2h['outcomes'] if o['name'] == 'Draw')
                a_o = next(o['price'] for o in h2h['outcomes'] if o['name'] == m['away_team'])
                
                o25_o, u25_o = None, None
                if totals:
                    o25_o = next((o['price'] for o in totals['outcomes'] if o['name'] == 'Over' and o.get('point') == 2.5), None)
                    u25_o = next((o['price'] for o in totals['outcomes'] if o['name'] == 'Under' and o.get('point') == 2.5), None)

                recs, scores, T = run_analysis_v69(h_o, d_o, a_o, o25_o, u25_o)
                
                start_dt = datetime.strptime(m['commence_time'], "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=pytz.utc).astimezone(tw_tz)
                
                # UI 渲染
                score_html = "".join([f"<div class='score-badge'>{s} ({p:.1%})</div>" for s, p in scores.items()])
                rec_html = ""
                for r in recs:
                    color = "#00ff88" if "實戰" in r['tag'] else "#58a6ff"
                    if "平衡" in r['tag']: color = "#8b949e"
                    rec_html += f"""
                    <div class="rec-box" style="border-color: {color}">
                        <span style="color:{color}; font-weight:bold;">[{r['tag']}]</span> {r['label']} 
                        <span style="float:right;">優勢: {r['edge']:+.1%} | 倉位: {r['stake']:.1%}</span>
                    </div>
                    """

                st.markdown(f"""
                <div class="master-card">
                    <div style="display:flex; justify-content:space-between; font-size:0.8rem; color:#8b949e;">
                        <span>🏆 {m['sport_title']} | 預期總進球: {T:.2f}</span>
                        <span>🕒 {start_dt.strftime('%m/%d %H:%M')}</span>
                    </div>
                    <div class="team-line">{m['home_team']} <span style="color:#444;">vs</span> {m['away_team']}</div>
                    <div style="margin-bottom: 10px;">{score_html}</div>
                    {rec_html}
                </div>
                """, unsafe_allow_html=True)
            except: continue

    with tab2:
        conn = sqlite3.connect('zeus_quant_v69.db')
        df = pd.read_sql_query("SELECT * FROM matches ORDER BY timestamp DESC LIMIT 50", conn)
        st.dataframe(df, use_container_width=True)
        conn.close()

if __name__ == "__main__":
    main()
