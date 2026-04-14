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
# 🧠 2. 修正後的專業量化核心
# ==========================================

def power_method_probs(odds):
    """
    【修正版】使用 root_scalar 避免維度廣播錯誤。
    精確還原真實機率，對抗 Favorite-Longshot Bias。
    """
    odds_arr = np.array(odds)
    try:
        # 定義求解函數：sum((1/odds)^k) - 1 = 0
        def func(k):
            return np.sum(np.power(1/odds_arr, k)) - 1.0
        
        # 使用穩定性最高的 brentq 演算法在區間 [0.1, 5.0] 尋找數值解
        res = root_scalar(func, bracket=[0.1, 5.0], method='brentq')
        if res.converged:
            k_sol = res.root
            return np.power(1/odds_arr, k_sol)
        else:
            raise ValueError("Convergence failed")
    except:
        # 降級方案：若數學求解失敗，使用標準等比例去水
        margin = np.sum(1/odds_arr)
        return (1/odds_arr) / margin

def apply_dixon_coles(matrix, l_h, l_a, rho=-0.1):
    """【修正矩陣】解決低比分預測偏差"""
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
    """【資金管理】1/4 凱利準則"""
    b = bookie_odds - 1
    p = my_prob
    q = 1 - p
    if b <= 0: return 0
    f_star = (b * p - q) / b
    return max(0, f_star * fraction)

def solve_implied_total(p_u25):
    """從大小球盤口反推預期總進球數 T"""
    def obj(T): return poisson.cdf(2, T) - p_u25
    try:
        return root_scalar(obj, bracket=[0.1, 8.0], method='brentq').root
    except: return 2.65

# ==========================================
# ⚡ 3. 核心運算邏輯
# ==========================================

def run_analysis(h_o, d_o, a_o, o25_o, u25_o):
    # 1. 真實機率還原 (Power Method)
    true_1x2 = power_method_probs([h_o, d_o, a_o])
    p_h, p_d, p_a = true_1x2
    
    # 2. 總進球 Lambda 反推
    p_u25 = 0.48
    if o25_o and u25_o:
        # 大小球也使用 Power Method 去水
        p_u25 = power_method_probs([o25_o, u25_o])[1]
    T = solve_implied_total(p_u25)
    
    # 3. 攻防 Lambda 分配
    ratio = p_h / p_a
    l_h = T * (ratio**0.75 / (ratio**0.75 + 1))
    l_a = T - l_h
    
    # 4. 生成 10x10 修正矩陣
    max_g = 10
    pmf_h = poisson.pmf(np.arange(max_g), l_h)
    pmf_a = poisson.pmf(np.arange(max_g), l_a)
    matrix = apply_dixon_coles(np.outer(pmf_h, pmf_a), l_h, l_a)
    
    # 5. 模型計算機率
    m_h, m_d, m_a = np.sum(np.tril(matrix, -1)), np.sum(np.diag(matrix)), np.sum(np.triu(matrix, 1))
    m_u25 = np.sum([matrix[i, j] for i in range(3) for j in range(3-i)])
    m_o25 = 1 - m_u25
    
    # 6. 優勢 (Edge) 與 凱利建議
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
        .edge-val { color: #00ff88; font-size: 0.85rem; font-weight: bold; margin-left: 5px; }
    </style>
    """, unsafe_allow_html=True)

# ==========================================
# 🖥️ 5. 主程式
# ==========================================
def main():
    apply_styles()
    tw_tz = pytz.timezone('Asia/Taipei')
    st.markdown("<h1 style='text-align:center; color:#8a2be2;'>⚛️ ZEUS QUANT TERMINAL v67.1</h1>", unsafe_allow_html=True)
    
    tab1, tab2, tab3 = st.tabs(["🎯 實時量化", "📚 數據覆盤", "⚙️ 系統診斷"])

    try: 
        api_key = st.secrets["ODDS_API_KEY"]
    except: 
        st.error("❌ 未偵測到 ODDS_API_KEY"); return

    with tab1:
        url = f"https://api.the-odds-api.com/v4/sports/soccer/odds/?apiKey={api_key}&regions=eu&markets=h2h,totals"
        try:
            res = requests.get(url)
            data = res.json()
            headers = res.headers
        except:
            st.error("API 連線失敗"); return

        if res.status_code != 200:
            st.error(f"API Error: {res.status_code}"); return
        
        st.markdown(f"<p style='color:#8b949e; font-family:monospace;'>最後更新: {datetime.now(tw_tz).strftime('%H:%M:%S')} | 剩餘額度: {headers.get('x-requests-remaining', 'N/A')}</p>", unsafe_allow_html=True)

        for m in data[:30]:
            try:
                bm = m.get('bookmakers')
                if not bm: continue
                
                # 提取數據
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

                # 執行修正後的量化運算
                recs, scores, T = run_analysis(h_o, d_o, a_o, o25_o, u25_o)
                
                start_dt = datetime.strptime(m['commence_time'], "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=pytz.utc).astimezone(tw_tz)
                time_label = start_dt.strftime("%m/%d %H:%M")

                # 資料庫 UPSERT
                conn = sqlite3.connect('zeus_quant.db')
                c = conn.cursor()
                m_id = f"{m['id']}_{start_dt.strftime('%m%d')}"
                pred_str = " | ".join([f"{r['label']}" for r in recs]) if recs else "無明顯優勢"
                stake_str = " | ".join([f"{r['stake']:.1%}" for r in recs]) if recs else "0%"
                
                c.execute("""INSERT INTO matches (match_id, league, home, away, prediction, stake, status, timestamp, start_time) 
                             VALUES (?,?,?,?,?,?,?,?,?) ON CONFLICT(match_id) DO UPDATE SET 
                             prediction=excluded.prediction, stake=excluded.stake, timestamp=excluded.timestamp""", 
                          (m_id, m['sport_title'], m['home_team'], m['away_team'], pred_str, stake_str, "待定", datetime.now(tw_tz).strftime('%Y-%m-%d %H:%M'), time_label))
                conn.commit(); conn.close()

                # UI 渲染
                score_html = "".join([f"<div class='score-badge'>{s} ({p:.1%})</div>" for s, p in scores.items()])
                rec_html = "".join([f"<div style='margin-top:8px;'>{r['label']} <span class='edge-val'>+{r['edge']:.1%}</span> <span class='stake-tag'>倉位: {r['stake']:.1%}</span></div>" for r in recs])
                
                st.markdown(f"""
                <div class="master-card">
                    <div style="display:flex; justify-content:space-between; font-size:0.8rem; color:#8b949e;">
                        <span>🏆 {m['sport_title']} | 預期總進球: {T:.2f}</span>
                        <span>🕒 {time_label}</span>
                    </div>
                    <div class="team-line">{m['home_team']} <span style="color:#444;">vs</span> {m['away_team']}</div>
                    <div style="margin-bottom: 10px;">{score_html}</div>
                    <div style="background: #21262d; padding: 10px; border-radius: 8px; border: 1px solid #30363d;">
                        {rec_html if recs else "<span style='color:#666;'>市場定價極其精準，無套利空間</span>"}
                    </div>
                </div>
                """, unsafe_allow_html=True)
            except Exception as e:
                # 即使單一賽事解析出錯，也不影響其他賽事顯示
                continue

    with tab2:
        st.markdown("### 📊 歷史數據檢視")
        conn = sqlite3.connect('zeus_quant.db')
        df = pd.read_sql_query("SELECT start_time, home, away, prediction, stake, status FROM matches ORDER BY timestamp DESC LIMIT 50", conn)
        st.data_editor(df, use_container_width=True, hide_index=True)
        conn.close()

    with tab3:
        st.markdown("### ⚙️ 核心引擎診斷")
        st.write(f"當前時區: `{tw_tz.zone}`")
        st.write("去水模型: `Power Method (root_scalar)`")
        st.write("修正係數: `Dixon-Coles (Rho: -0.1)`")
        if st.button("🗑️ 清空歷史數據庫"):
            conn = sqlite3.connect('zeus_quant.db'); c = conn.cursor(); c.execute("DELETE FROM matches"); conn.commit(); conn.close()
            st.rerun()

if __name__ == "__main__":
    main()
