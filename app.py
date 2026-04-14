import streamlit as st
import requests
import numpy as np
import pandas as pd
import sqlite3
import pytz
from datetime import datetime
from scipy.stats import poisson
from scipy.optimize import root_scalar, fsolve

# ==========================================
# 🔑 1. 系統初始化與資料庫 (支持 UPSERT)
# ==========================================
def init_db():
    conn = sqlite3.connect('zeus_quant.db', check_same_thread=False)
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS matches 
                 (match_id TEXT PRIMARY KEY, league TEXT, home TEXT, away TEXT, 
                  prediction TEXT, stake TEXT, status TEXT, 
                  timestamp TEXT, start_time TEXT)''')
    conn.commit()
    conn.close()

init_db()

# ==========================================
# 🧠 2. 專業量化數學核心 (The Quant Engine)
# ==========================================

def power_method_probs(odds):
    """
    【去水優化】使用 Power Method 尋找隱含機率。
    相比等比例分配，它能更準確地修正 Favorite-Longshot Bias。
    """
    try:
        def func(k):
            return np.sum(np.power(1/np.array(odds), k)) - 1.0
        k_sol = fsolve(func, 1.0)[0]
        return np.power(1/np.array(odds), k_sol)
    except:
        margin = np.sum(1/np.array(odds))
        return (1/np.array(odds)) / margin

def apply_dixon_coles(matrix, l_h, l_a, rho=-0.1):
    """
    【矩陣修正】Dixon-Coles 修正，解決泊松分佈對低比分 (0:0, 1:1 等) 估計不足的問題。
    """
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

def calculate_kelly(my_prob, bookie_odds, fraction=0.25):
    """
    【資金管理】凱利準則。建議下注比例。
    使用 1/4 Kelly 確保在模型誤差下依然能穩健成長。
    """
    b = bookie_odds - 1
    p = my_prob
    q = 1 - p
    if b <= 0: return 0
    f_star = (b * p - q) / b
    return max(0, f_star * fraction)

def solve_implied_total(p_u25):
    """反推預期總進球數 T"""
    def obj(T): return poisson.cdf(2, T) - p_u25
    try:
        return root_scalar(obj, bracket=[0.1, 8.0], method='brentq').root
    except: return 2.65

# ==========================================
# ⚡ 3. 數據抓取與處理
# ==========================================
@st.cache_data(ttl=600)
def fetch_data(api_key):
    url = f"https://api.the-odds-api.com/v4/sports/soccer/odds/?apiKey={api_key}&regions=eu&markets=h2h,totals"
    try:
        res = requests.get(url)
        return res.status_code, res.json(), res.headers
    except: return 500, {}, {}

def run_analysis(h_o, d_o, a_o, o25_o, u25_o):
    # 1. 真實機率還原
    true_1x2 = power_method_probs([h_o, d_o, a_o])
    p_h, p_d, p_a = true_1x2
    
    # 2. 總進球 Lambda 反推
    p_u25 = 0.48
    if o25_o and u25_o:
        p_u25 = power_method_probs([o25_o, u25_o])[1]
    T = solve_implied_total(p_u25)
    
    # 3. 攻防分配 (Dixon-Coles 修正比例)
    ratio = p_h / p_a
    l_h = T * (ratio**0.75 / (ratio**0.75 + 1))
    l_a = T - l_h
    
    # 4. 生成修正矩陣
    max_g = 10
    pmf_h = poisson.pmf(np.arange(max_g), l_h)
    pmf_a = poisson.pmf(np.arange(max_g), l_a)
    matrix = apply_dixon_coles(np.outer(pmf_h, pmf_a), l_h, l_a)
    
    # 5. 模型數據提取
    m_h, m_d, m_a = np.sum(np.tril(matrix, -1)), np.sum(np.diag(matrix)), np.sum(np.triu(matrix, 1))
    m_u25 = np.sum([matrix[i, j] for i in range(3) for j in range(3-i)])
    m_o25 = 1 - m_u25
    
    # 6. Edge 與 Kelly 計算
    targets = [
        ("🏠 主勝", m_h, h_o), ("🤝 和局", m_d, d_o), ("🚀 客勝", m_a, a_o),
        ("🔥 大 2.5", m_o25, o25_o), ("🛡️ 小 2.5", m_u25, u25_o)
    ]
    
    recs = []
    for label, prob, odds in targets:
        if odds and odds > 0:
            edge = prob - (1/odds)
            if edge > 0.02: # 門檻 2%
                stake = calculate_kelly(prob, odds)
                if stake > 0.005:
                    recs.append({"label": label, "edge": edge, "stake": stake})
    
    # 波膽 Top 3
    scores = {}
    idx = np.argsort(matrix, axis=None)[::-1][:3]
    for i in idx:
        r, c = np.unravel_index(i, matrix.shape)
        scores[f"{r}:{c}"] = matrix[r, c]
        
    return recs, scores, T

# ==========================================
# 🎨 4. UI 視覺樣式
# ==========================================
def apply_styles():
    st.markdown("""
    <style>
        .stApp { background-color: #0d1117; color: #e6edf3; }
        .master-card { background: #161b22; border: 1px solid #30363d; border-radius: 12px; padding: 20px; margin-bottom: 20px; border-left: 6px solid #8a2be2; }
        .team-line { font-size: 1.3rem; font-weight: 800; margin: 12px 0; color: #ffffff; }
        .score-badge { background: #21262d; color: #58a6ff; padding: 4px 10px; border-radius: 5px; font-size: 0.85rem; border: 1px solid #30363d; margin-right: 8px; display: inline-block; font-family: monospace; }
        .stake-tag { background: #8a2be2; color: white; padding: 2px 8px; border-radius: 4px; font-size: 0.75rem; font-weight: bold; }
        .edge-val { color: #00ff88; font-size: 0.8rem; font-weight: bold; }
    </style>
    """, unsafe_allow_html=True)

# ==========================================
# 🖥️ 5. 主程式入口
# ==========================================
def main():
    apply_styles()
    tw_tz = pytz.timezone('Asia/Taipei')
    st.markdown("<h1 style='text-align:center; color:#8a2be2;'>⚛️ ZEUS QUANT TERMINAL v67</h1>", unsafe_allow_html=True)
    
    tab1, tab2, tab3 = st.tabs(["🎯 實時量化", "📚 數據覆盤", "⚙️ 系統診斷"])

    try: api_key = st.secrets["ODDS_API_KEY"]
    except: st.error("Missing API Key"); return

    with tab1:
        code, data, headers = fetch_data(api_key)
        if code != 200: st.error(f"API Error: {code}"); return
        
        st.markdown(f"<p style='color:#8b949e; font-family:monospace;'>系統時區: {tw_tz.zone} | 額度剩餘: {headers.get('x-requests-remaining', 'N/A')}</p>", unsafe_allow_html=True)

        for m in data[:30]:
            try:
                bm = m.get('bookmakers')
                if not bm: continue
                
                # 提取 1X2 與 Totals
                h2h = next((mk for mk in bm[0]['markets'] if mk['key'] == 'h2h'), None)
                totals = next((mk for mk in bm[0]['markets'] if mk['key'] == 'totals'), None)
                if not h2h: continue
                
                h_o = next(o['price'] for o in h2h['outcomes'] if o['name'] == m['home_team'])
                d_o = next(o['price'] for o in h2h['outcomes'] if o['name'] == 'Draw')
                a_o = next(o['price'] for o in h2h['outcomes'] if o['name'] == m['away_team'])
                
                o25_o, u25_o = None, None
                if totals:
                    o25_o = next((o['price'] for o in totals['outcomes'] if o['name'] == 'Over' and o.get('point') == 2.5), None)
                    u25_o = next((o['price'] for o in totals['outcomes'] if o['name'] == 'Under' and o.get('point') == 2.5), None)

                # 量化運算
                recs, scores, T = run_analysis(h_o, d_o, a_o, o25_o, u25_o)
                
                start_dt = datetime.strptime(m['commence_time'], "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=pytz.utc).astimezone(tw_tz)
                time_label = start_dt.strftime("%m/%d %H:%M")

                # 資料庫 UPSERT
                conn = sqlite3.connect('zeus_quant.db')
                c = conn.cursor()
                m_id = f"{m['id']}_{start_dt.strftime('%m%d')}"
                pred_str = " | ".join([f"{r['label']}" for r in recs]) if recs else "無套利價值"
                stake_str = " | ".join([f"{r['stake']:.1%}" for r in recs]) if recs else "0%"
                
                c.execute("""INSERT INTO matches (match_id, league, home, away, prediction, stake, status, timestamp, start_time) 
                             VALUES (?,?,?,?,?,?,?,?,?) ON CONFLICT(match_id) DO UPDATE SET 
                             prediction=excluded.prediction, stake=excluded.stake, timestamp=excluded.timestamp""", 
                          (m_id, m['sport_title'], m['home_team'], m['away_team'], pred_str, stake_str, "待定", datetime.now(tw_tz).strftime('%Y-%m-%d %H:%M'), time_label))
                conn.commit(); conn.close()

                # UI 渲染
                score_html = "".join([f"<div class='score-badge'>{s} ({p:.1%})</div>" for s, p in scores.items()])
                rec_html = "".join([f"<div style='margin-top:8px;'>{r['label']} <span class='edge-val'>+{r['edge']:.1%}</span> <span class='stake-tag'>建議倉位: {r['stake']:.1%}</span></div>" for r in recs])
                
                st.markdown(f"""
                <div class="master-card">
                    <div style="display:flex; justify-content:space-between; font-size:0.8rem; color:#8b949e;">
                        <span>🏆 {m['sport_title']} | 預期總進球: {T:.2f}</span>
                        <span>🕒 {time_label}</span>
                    </div>
                    <div class="team-line">{m['home_team']} <span style="color:#444;">vs</span> {m['away_team']}</div>
                    <div style="margin-bottom: 10px;">{score_html}</div>
                    <div style="background: #21262d; padding: 10px; border-radius: 8px;">
                        {rec_html if recs else "<span style='color:#666;'>⚠️ 市場效率過高，目前無明顯優勢</span>"}
                    </div>
                </div>
                """, unsafe_allow_html=True)
            except: continue

    with tab2:
        st.markdown("### 📊 歷史數據與倉位管理")
        conn = sqlite3.connect('zeus_quant.db')
        df = pd.read_sql_query("SELECT start_time, home, away, prediction, stake, status FROM matches ORDER BY timestamp DESC LIMIT 50", conn)
        st.data_editor(df, use_container_width=True, hide_index=True)
        conn.close()

    with tab3:
        st.markdown("### ⚙️ 系統核心狀態")
        st.code(f"Timezone: {tw_tz.zone}\nEngine: Dixon-Coles + Power Method + Kelly\nStatus: Online")
        if st.button("🔴 重置系統資料庫"):
            conn = sqlite3.connect('zeus_quant.db'); c = conn.cursor(); c.execute("DELETE FROM matches"); conn.commit(); conn.close()
            st.rerun()

if __name__ == "__main__":
    main()
