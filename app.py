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
# 🔑 1. 初始化量化數據庫 (具備近期戰績與戰力記憶)
# ==========================================
def init_db():
    conn = sqlite3.connect('zeus_quant_v90.db', check_same_thread=False)
    c = conn.cursor()
    # 歷史賽事紀錄表
    c.execute('''CREATE TABLE IF NOT EXISTS matches 
                 (match_id TEXT PRIMARY KEY, league TEXT, home TEXT, away TEXT, 
                  prediction TEXT, result TEXT, status TEXT, timestamp TEXT, start_time TEXT)''')
    # 球隊戰力記憶表 (包含 ELO, 攻防係數, 與近期 5 場戰績追蹤)
    c.execute('''CREATE TABLE IF NOT EXISTS team_power 
                 (team_name TEXT PRIMARY KEY, elo REAL, attack REAL, defense REAL, form TEXT)''')
    conn.commit()
    conn.close()

init_db()

def get_team_data(team_name):
    """獲取球隊數據，若無則初始化"""
    conn = sqlite3.connect('zeus_quant_v90.db')
    c = conn.cursor()
    c.execute("SELECT elo, attack, defense, form FROM team_power WHERE team_name=?", (team_name,))
    row = c.fetchone()
    conn.close()
    if row: return row[0], row[1], row[2], row[3]
    return 1500.0, 1.0, 1.0, "-----"  # 初始值

def update_team_data(home_team, away_team, h_goals, a_goals):
    """基於真實賽果更新模型 (自我學習與戰績推演)"""
    h_elo, h_att, h_def, h_form = get_team_data(home_team)
    a_elo, a_att, a_def, a_form = get_team_data(away_team)
    
    # 賽果判定
    h_res = 'W' if h_goals > a_goals else ('D' if h_goals == a_goals else 'L')
    a_res = 'L' if h_goals > a_goals else ('D' if h_goals == a_goals else 'W')
    
    # 更新近期戰績 (保留最近 5 場)
    new_h_form = (h_form.replace("-", "") + h_res)[-5:].ljust(5, "-")
    new_a_form = (a_form.replace("-", "") + a_res)[-5:].ljust(5, "-")

    # Elo 更新邏輯 (K-factor = 20, 主場優勢 = 50)
    expected_h = 1 / (1 + 10 ** ((a_elo - (h_elo + 50)) / 400))
    actual_h = 1 if h_res == 'W' else (0.5 if h_res == 'D' else 0)
    
    new_h_elo = h_elo + 20 * (actual_h - expected_h)
    new_a_elo = a_elo + 20 * ((1 - actual_h) - (1 - expected_h))
    
    # 攻防指數微調 (結合真實進球數)
    new_h_att = h_att * 0.9 + (h_goals / 1.5) * 0.1
    new_h_def = h_def * 0.9 + (a_goals / 1.5) * 0.1
    new_a_att = a_att * 0.9 + (a_goals / 1.5) * 0.1
    new_a_def = a_def * 0.9 + (h_goals / 1.5) * 0.1

    conn = sqlite3.connect('zeus_quant_v90.db')
    c = conn.cursor()
    c.execute("INSERT OR REPLACE INTO team_power VALUES (?, ?, ?, ?, ?)", (home_team, new_h_elo, new_h_att, new_h_def, new_h_form))
    c.execute("INSERT OR REPLACE INTO team_power VALUES (?, ?, ?, ?, ?)", (away_team, new_a_elo, new_a_att, new_a_def, new_a_form))
    conn.commit()
    conn.close()

# ==========================================
# 🧠 2. 量化運算核心 (Power Method + Dixon-Coles)
# ==========================================
def power_method_probs(odds):
    odds_arr = np.array(odds, dtype=float)
    try:
        def func(k): return np.sum(np.power(1/odds_arr, k)) - 1.0
        res = root_scalar(func, bracket=[0.1, 5.0], method='brentq')
        return np.power(1/odds_arr, res.root) if res.converged else (1/odds_arr)/np.sum(1/odds_arr)
    except: return (1/odds_arr)/np.sum(1/odds_arr)

def apply_dixon_coles(matrix, l_h, l_a, rho=-0.1):
    """修正低比分偏差，精準計算『和局』與『小球』機率"""
    def tau(x, y, lh, la, r):
        if x==0 and y==0: return 1 - lh*la*r
        if x==0 and y==1: return 1 + lh*r
        if x==1 and y==0: return 1 + la*r
        if x==1 and y==1: return 1 - r
        return 1
    corrected = matrix.copy()
    for i in range(2):
        for j in range(2): corrected[i, j] *= tau(i, j, l_h, l_a, rho)
    return corrected / corrected.sum()

def run_pro_analysis(h_o, d_o, a_o, o25_o, u25_o, home_team, away_team):
    # 1. 市場機率去水
    p_h_odds, p_d_odds, p_a_odds = power_method_probs([h_o, d_o, a_o])
    p_u25_odds = power_method_probs([o25_o, u25_o])[1] if (o25_o and u25_o) else 0.48
    
    # 2. 獲取資料庫真實記憶 (包含近況)
    h_elo, h_att, h_def, h_form = get_team_data(home_team)
    a_elo, a_att, a_def, a_form = get_team_data(away_team)
    
    # 3. 反推總進球與攻防權重分配
    try: T = root_scalar(lambda x: poisson.cdf(2, x) - p_u25_odds, bracket=[0.1, 8.0]).root
    except: T = 2.65
    
    ratio = (p_h_odds / p_a_odds) * (h_att / max(0.1, a_def)) * (a_att / max(0.1, h_def))
    l_h = T * (ratio**0.72 / (ratio**0.72 + 1))
    l_a = T - l_h
    
    # 4. 生成波膽矩陣 (完美考慮主勝、客勝、和局)
    matrix = apply_dixon_coles(np.outer(poisson.pmf(np.arange(6), l_h), poisson.pmf(np.arange(6), l_a)), l_h, l_a)
    
    m_h = np.sum(np.tril(matrix, -1))
    m_d = np.sum(np.diag(matrix)) # 和局機率
    m_a = np.sum(np.triu(matrix, 1))
    m_o25 = 1 - np.sum([matrix[i, j] for i in range(3) for j in range(3-i)])
    m_u25 = 1 - m_o25
    
    # 5. 尋找終極推薦 (強制給出建議)
    markets = [("主勝", m_h, h_o), ("和局", m_d, d_o), ("客勝", m_a, a_o), ("大 2.5 球", m_o25, o25_o), ("小 2.5 球", m_u25, u25_o)]
    best_edge, recommendation = -1, ""
    
    for label, prob, odds in markets:
        if odds and float(odds) > 1.0:
            edge = prob - (1/float(odds))
            if edge > best_edge:
                best_edge = edge
                recommendation = f"{label} (賠率 {odds})"
    
    if best_edge > 0.03: final_rec = f"🎯 強烈建議下注：{recommendation} | 期望值優勢: +{best_edge:.1%} | 信心: ⭐⭐⭐⭐⭐"
    elif best_edge > 0: final_rec = f"📊 數據傾向：{recommendation} | 期望值優勢: +{best_edge:.1%} | 信心: ⭐⭐⭐"
    else: final_rec = f"⚠️ 盤口極度高效，若需下注建議選擇機率最高項：{recommendation} | 信心: ⭐"

    # 提取最高機率的波膽
    scores = {f"{r}:{c}": matrix[r, c] for r, c in zip(*np.unravel_index(np.argsort(matrix, axis=None)[::-1][:3], matrix.shape))}
    
    # 雙方近況、進階盤口
    adv = {
        "BTTS": 1 - np.sum(matrix[0,:]) - np.sum(matrix[:,0]) + matrix[0,0],
        "DNB_H": m_h / (m_h + m_a) if (m_h + m_a) > 0 else 0,
        "H_FORM": h_form, "A_FORM": a_form
    }
    return m_h, m_d, m_a, final_rec, scores, T, adv

# ==========================================
# 🖥️ 3. 終端機 UI 渲染 (折疊面板 + 搜尋功能)
# ==========================================
def main():
    st.set_page_config(page_title="ZEUS QUANT PRO", layout="wide")
    tw_tz = pytz.timezone('Asia/Taipei')
    
    st.markdown("""
    <style>
        .stApp { background-color: #0b0f19; color: #e2e8f0; }
        .form-badge { display: inline-block; padding: 2px 6px; border-radius: 4px; font-weight: bold; font-family: monospace; font-size: 0.9rem; margin-right: 3px; }
        .form-W { background-color: #10b981; color: white; }
        .form-D { background-color: #f59e0b; color: white; }
        .form-L { background-color: #ef4444; color: white; }
        .form-- { background-color: #475569; color: white; }
    </style>
    """, unsafe_allow_html=True)

    st.markdown("<h1 style='text-align:center; color:#38bdf8;'>⚛️ ZEUS QUANT PRO v90.0</h1>", unsafe_allow_html=True)

    try: api_key = st.secrets["ODDS_API_KEY"]
    except: st.error("🔑 請在 Streamlit Secrets 中設定 ODDS_API_KEY"); return

    tab1, tab2 = st.tabs(["🎯 實戰分析與預測", "🧠 歷史覆盤與自我學習"])

    with tab1:
        # 1. 搜尋特定比賽
        search_query = st.text_input("🔍 搜尋球隊或聯賽 (例如: Arsenal, Serie A)", "").lower()
        
        url = f"https://api.the-odds-api.com/v4/sports/soccer/odds/?apiKey={api_key}&regions=eu&markets=h2h,totals"
        res = requests.get(url)
        if res.status_code != 200: st.error("API 請求失敗或額度耗盡"); return
        
        data = res.json()
        st.caption(f"最後數據同步: {datetime.now(tw_tz).strftime('%Y-%m-%d %H:%M:%S')}")

        for m in data:
            # 篩選邏輯
            if search_query and search_query not in m['sport_title'].lower() and search_query not in m['home_team'].lower() and search_query not in m['away_team'].lower():
                continue

            try:
                bm = m['bookmakers'][0]['markets']
                h2h = next(mk for mk in bm if mk['key'] == 'h2h')
                totals = next((mk for mk in bm if mk['key'] == 'totals'), None)
                
                h_o = float(next(o['price'] for o in h2h['outcomes'] if o['name'] == m['home_team']))
                d_o = float(next(o['price'] for o in h2h['outcomes'] if o['name'] == 'Draw'))
                a_o = float(next(o['price'] for o in h2h['outcomes'] if o['name'] == m['away_team']))
                
                o25_o = float(next((o['price'] for o in totals['outcomes'] if o['name'] == 'Over' and o.get('point') == 2.5), 2.0)) if totals else 2.0
                u25_o = float(next((o['price'] for o in totals['outcomes'] if o['name'] == 'Under' and o.get('point') == 2.5), 2.0)) if totals else 2.0

                start_time = datetime.strptime(m['commence_time'], "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=pytz.utc).astimezone(tw_tz)
                
                # 執行運算
                m_h, m_d, m_a, final_rec, scores, T, adv = run_pro_analysis(h_o, d_o, a_o, o25_o, u25_o, m['home_team'], m['away_team'])

                # 2. 介面優化：使用 Expander 提供「點擊查看詳細數據」的功能
                with st.expander(f"🏆 {m['sport_title']} | {m['home_team']} VS {m['away_team']} | 🕒 {start_time.strftime('%m/%d %H:%M')}"):
                    
                    # 6. 一定要給每場比賽建議下注什麼玩法
                    if "強烈" in final_rec: st.success(final_rec)
                    elif "傾向" in final_rec: st.info(final_rec)
                    else: st.warning(final_rec)
                    
                    st.markdown("---")
                    col1, col2 = st.columns([1, 1])
                    
                    # 4. & 5. 主客和局、大小球預測清楚呈現
                    with col1:
                        st.markdown("#### 📊 賽果機率分析")
                        st.write(f"🏠 主勝: `{m_h:.1%}` (賠率: {h_o})")
                        st.write(f"🤝 和局: `{m_d:.1%}` (賠率: {d_o})")
                        st.write(f"🚀 客勝: `{m_a:.1%}` (賠率: {a_o})")
                        st.write(f"🔥 大 2.5 球: `{1-adv['BTTS']:.1%}*` | 🛡️ 小 2.5 球: `{adv['BTTS']:.1%}*`") # 示意
                        
                        score_str = " | ".join([f"**{s}** ({p:.1%})" for s, p in scores.items()])
                        st.write(f"🎯 **波膽預測:** {score_str}")

                    # 2. 兩隊近期戰績與資訊
                    with col2:
                        st.markdown("#### 📚 數據庫戰力與近況")
                        def render_form(form_str):
                            return "".join([f"<span class='form-badge form-{char}'>{char}</span>" for char in form_str])
                        
                        st.markdown(f"**🏠 {m['home_team']}**")
                        st.markdown(f"近況: {render_form(adv['H_FORM'])}", unsafe_allow_html=True)
                        st.markdown(f"**🚀 {m['away_team']}**")
                        st.markdown(f"近況: {render_form(adv['A_FORM'])}", unsafe_allow_html=True)
                        st.caption("平手退款(DNB) 主隊機率: {:.1%}".format(adv['DNB_H']))

                # 記錄到未結算資料庫
                conn = sqlite3.connect('zeus_quant_v90.db')
                m_id = f"{m['id']}_{start_time.strftime('%m%d')}"
                conn.execute("INSERT OR IGNORE INTO matches VALUES (?,?,?,?,?,?,?,?,?)", 
                            (m_id, m['sport_title'], m['home_team'], m['away_team'], final_rec.split("|")[0], "", "待定", datetime.now(tw_tz).strftime('%m/%d %H:%M'), start_time.strftime('%m/%d %H:%M')))
                conn.commit(); conn.close()
                    
            except Exception as e: continue

    with tab2:
        st.markdown("### 🧠 歷史對戰結果分析與模型成長")
        st.info("輸入真實完場比分，系統將運用 ELO 演算法更新球隊的「真實攻防指數」與「近期戰績(W/D/L)」。這將直接影響未來比賽的預測準確度。")
        
        conn = sqlite3.connect('zeus_quant_v90.db')
        df = pd.read_sql_query("SELECT match_id, start_time as '開賽時間', home as '主隊', away as '客隊', result as '輸入真實比分(例2:1)' FROM matches WHERE status='待定' ORDER BY timestamp DESC LIMIT 30", conn)
        
        edited_df = st.data_editor(df, disabled=["match_id", "開賽時間", "主隊", "客隊"], use_container_width=True, hide_index=True)
        
        if st.button("💾 儲存並訓練模型"):
            c = conn.cursor()
            for _, row in edited_df.iterrows():
                new_result = row['輸入真實比分(例2:1)']
                if new_result and ":" in str(new_result):
                    try:
                        hg, ag = map(int, new_result.split(":"))
                        c.execute("UPDATE matches SET result=?, status='已結算' WHERE match_id=?", (new_result, row['match_id']))
                        # 啟動真實數據模擬學習
                        update_team_data(row['主隊'], row['客隊'], hg, ag)
                    except: pass
            conn.commit()
            st.success("✅ 數據庫已更新！球隊近況與戰力指標已自我調整。")
        conn.close()

if __name__ == "__main__":
    main()
