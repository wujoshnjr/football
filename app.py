import streamlit as st
import requests
import numpy as np
import pandas as pd
import sqlite3
import pytz
from datetime import datetime, timedelta
from scipy.stats import poisson
from scipy.optimize import root_scalar

# ==========================================
# 🔑 1. 系統初始化與資料庫 (UPSERT 架構)
# ==========================================
def init_db():
    conn = sqlite3.connect('zeus_master.db', check_same_thread=False)
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS matches 
                 (match_id TEXT PRIMARY KEY, league TEXT, home TEXT, away TEXT, 
                  prediction TEXT, stake TEXT, status TEXT, 
                  timestamp TEXT, start_time TEXT)''')
    conn.commit()
    conn.close()

init_db()

# ==========================================
# 🧠 2. 專業量化運算核心 (Power Method + Dixon-Coles)
# ==========================================

def power_method_probs(odds):
    """使用 Power Method 還原真實機率，解決 Favorite-Longshot Bias"""
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
    """低比分修正係數，提升平局預測精度"""
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

def calculate_kelly(my_prob, bookie_odds, fraction=0.25):
    """1/4 凱利準則資金管理"""
    if not bookie_odds or bookie_odds <= 1: return 0
    b = bookie_odds - 1
    f_star = (b * my_prob - (1 - my_prob)) / b
    return max(0, f_star * fraction)

# ==========================================
# ⚡ 3. 核心數據處理流
# ==========================================

@st.cache_data(ttl=600) # 10分鐘 API 緩存，保護額度
def fetch_api_data(api_key):
    url = f"https://api.the-odds-api.com/v4/sports/soccer/odds/?apiKey={api_key}&regions=eu&markets=h2h,totals"
    try:
        res = requests.get(url)
        return res.status_code, res.json(), res.headers
    except:
        return 500, {}, {}

def run_quant_analysis(h_o, d_o, a_o, o25_o, u25_o):
    # 1. 真實機率去水
    p_h, p_d, p_a = power_method_probs([h_o, d_o, a_o])
    p_u25 = power_method_probs([o25_o, u25_o])[1] if (o25_o and u25_o) else 0.48
    
    # 2. 反推總進球 Lambda
    T = solve_implied_total(p_u25)
    
    # 3. 分配攻防 Lambda (考慮強隊權重提升)
    ratio = p_h / p_a
    l_h = T * (ratio**0.72 / (ratio**0.72 + 1))
    l_a = T - l_h
    
    # 4. 生成修正機率矩陣
    max_g = 10
    pmf_h = poisson.pmf(np.arange(max_g), l_h)
    pmf_a = poisson.pmf(np.arange(max_g), l_a)
    matrix = apply_dixon_coles(np.outer(pmf_h, pmf_a), l_h, l_a)
    
    # 5. 計算模型結果
    m_h, m_d, m_a = np.sum(np.tril(matrix, -1)), np.sum(np.diag(matrix)), np.sum(np.triu(matrix, 1))
    m_u25 = np.sum([matrix[i, j] for i in range(3) for j in range(3-i)])
    m_o25 = 1 - m_u25
    
    # 6. Edge 判定與凱利
    targets = [
        ("🏠 主勝", m_h, h_o), ("🤝 和局", m_d, d_o), ("🚀 客勝", m_a, a_o),
        ("🔥 大 2.5", m_o25, o25_o), ("🛡️ 小 2.5", m_u25, u25_o)
    ]
    
    recs = []
    for label, prob, odds in targets:
        if odds:
            edge = prob - (1/odds)
            if edge > 0.025: # 門檻 2.5%
                stake = calculate_kelly(prob, odds)
                if stake > 0.005:
                    recs.append({"label": label, "edge": edge, "stake": stake})
    
    # 提取最高機率比分
    scores = {}
    top_indices = np.argsort(matrix, axis=None)[::-1][:3]
    for i in top_indices:
        r, c = np.unravel_index(i, matrix.shape)
        scores[f"{r}:{c}"] = matrix[r, c]
        
    return recs, scores, T

# ==========================================
# 🖥️ 4. Streamlit UI 介面
# ==========================================
def main():
    st.set_page_config(page_title="ZEUS QUANT MASTER", layout="wide")
    tw_tz = pytz.timezone('Asia/Taipei')
    
    st.markdown("""
    <style>
        .stApp { background-color: #0d1117; color: #e6edf3; }
        .master-card { background: #161b22; border: 1px solid #30363d; border-radius: 12px; padding: 20px; margin-bottom: 20px; border-left: 6px solid #8a2be2; }
        .team-title { font-size: 1.4rem; font-weight: 800; color: #ffffff; margin-bottom: 10px; }
        .score-badge { background: #21262d; color: #58a6ff; padding: 4px 12px; border-radius: 6px; font-size: 0.9rem; margin-right: 8px; border: 1px solid #30363d; font-family: 'Courier New', monospace; }
        .rec-item { background: #23863622; border: 1px solid #238636; padding: 8px; border-radius: 6px; margin-top: 8px; }
        .stake-val { color: #f1c40f; font-weight: bold; }
    </style>
    """, unsafe_allow_html=True)

    st.markdown("<h1 style='text-align:center; color:#8a2be2;'>⚛️ ZEUS QUANT TERMINAL v68.0</h1>", unsafe_allow_html=True)
    
    tab1, tab2, tab3 = st.tabs(["🎯 實時量化預測", "📚 歷史覆盤", "⚙️ 系統診斷"])

    try: api_key = st.secrets["ODDS_API_KEY"]
    except: st.error("🔑 請在 Secrets 中設定 ODDS_API_KEY"); return

    with tab1:
        status, data, headers = fetch_api_data(api_key)
        if status != 200: st.error(f"API 請求失敗: {status}"); return
        
        st.markdown(f"<p style='color:#8b949e; font-family:monospace;'>最後更新: {datetime.now(tw_tz).strftime('%H:%M:%S')} | 💎 剩餘額度: {headers.get('x-requests-remaining', 'N/A')}</p>", unsafe_allow_html=True)

        for m in data[:25]:
            try:
                bm = m.get('bookmakers')
                if not bm: continue
                
                # 數據解析
                h2h = next((mk for mk in bm[0]['markets'] if mk['key'] == 'h2h'), None)
                totals = next((mk for mk in bm[0]['markets'] if mk['key'] == 'totals'), None)
                if not h2h: continue
                
                h_o = next(o['price'] for o in h2h['outcomes'] if o['name'] == m['home_team'])
                d_o = next(o['price'] for o in h2h['outcomes'] if o['name'] == 'Draw')
                a_o = next(o['price'] for o in h2h['outcomes'] if o['name'] == m['away_team'])
                
                o25_o = next((o['price'] for o in totals['outcomes'] if o['name'] == 'Over' and o.get('point') == 2.5), None) if totals else None
                u25_o = next((o['price'] for o in totals['outcomes'] if o['name'] == 'Under' and o.get('point') == 2.5), None) if totals else None

                # 量化計算
                recs, scores, T = run_quant_analysis(h_o, d_o, a_o, o25_o, u25_o)
                
                start_dt = datetime.strptime(m['commence_time'], "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=pytz.utc).astimezone(tw_tz)
                time_label = start_dt.strftime("%m/%d %H:%M")

                # 資料庫 UPSERT
                m_id = f"{m['id']}_{start_dt.strftime('%m%d')}"
                pred_str = " | ".join([r['label'] for r in recs]) if recs else "無顯著優勢"
                stake_str = " | ".join([f"{r['stake']:.1%}" for r in recs]) if recs else "0%"
                
                conn = sqlite3.connect('zeus_master.db')
                conn.execute("""INSERT INTO matches (match_id, league, home, away, prediction, stake, status, timestamp, start_time) 
                             VALUES (?,?,?,?,?,?,?,?,?) ON CONFLICT(match_id) DO UPDATE SET 
                             prediction=excluded.prediction, stake=excluded.stake, timestamp=excluded.timestamp""", 
                          (m_id, m['sport_title'], m['home_team'], m['away_team'], pred_str, stake_str, "待定", datetime.now(tw_tz).strftime('%Y-%m-%d %H:%M'), time_label))
                conn.commit(); conn.close()

                # UI 渲染
                score_html = "".join([f"<span class='score-badge'>{s} ({p:.1%})</span>" for s, p in scores.items()])
                rec_html = "".join([f"<div class='rec-item'>✅ {r['label']} | <span style='color:#00ff88;'>Edge: +{r['edge']:.1%}</span> | 建議倉位: <span class='stake-val'>{r['stake']:.1%}</span></div>" for r in recs])
                
                st.markdown(f"""
                <div class="master-card">
                    <div style="display:flex; justify-content:space-between; font-size:0.8rem; color:#8b949e; margin-bottom:8px;">
                        <span>🏆 {m['sport_title']} | 🎯 隱含總進球: {T:.2f}</span>
                        <span>🕒 {time_label}</span>
                    </div>
                    <div class="team-title">{m['home_team']} <span style="color:#444; font-size:1rem;">VS</span> {m['away_team']}</div>
                    <div style="margin-bottom: 12px;">{score_html}</div>
                    {rec_html if recs else "<div style='color:#666; font-size:0.9rem; padding:8px;'>⚠️ 市場定價高效，暫無正期望值套利空間</div>"}
                </div>
                """, unsafe_allow_html=True)
            except: continue

    with tab2:
        st.markdown("### 📊 歷史數據覆盤中心")
        conn = sqlite3.connect('zeus_master.db')
        df = pd.read_sql_query("SELECT start_time as '比賽時間', league as '聯賽', home as '主隊', away as '客隊', prediction as '預測建議', stake as '凱利倉位', status as '狀態' FROM matches ORDER BY timestamp DESC LIMIT 100", conn)
        st.data_editor(df, use_container_width=True, hide_index=True)
        conn.close()

    with tab3:
        st.markdown("### ⚙️ 量化引擎診斷與控制")
        col1, col2 = st.columns(2)
        col1.metric("當前時區", tw_tz.zone)
        col1.write("演算法: `Bivariate Poisson + Dixon Coles`")
        col2.write("去水模型: `Power Method Solver`")
        if st.button("🗑️ 危險操作：清空所有數據"):
            conn = sqlite3.connect('zeus_master.db'); conn.execute("DELETE FROM matches"); conn.commit(); conn.close()
            st.success("資料庫已清空"); st.rerun()

if __name__ == "__main__":
    main()
