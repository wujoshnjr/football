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
# 🔑 1. 核心數據庫與自我學習引擎
# ==========================================
def init_db():
    conn = sqlite3.connect('zeus_ultimate_v92.db', check_same_thread=False)
    c = conn.cursor()
    # 儲存賽事與預測結果
    c.execute('''CREATE TABLE IF NOT EXISTS matches 
                 (match_id TEXT PRIMARY KEY, league TEXT, home TEXT, away TEXT, 
                  prediction TEXT, result TEXT, status TEXT, timestamp TEXT, start_time TEXT)''')
    # 儲存球隊長期記憶：ELO、進攻力、防禦力、近五場表現
    c.execute('''CREATE TABLE IF NOT EXISTS team_power 
                 (team_name TEXT PRIMARY KEY, elo REAL, attack REAL, defense REAL, form TEXT)''')
    conn.commit()
    conn.close()

init_db()

def get_team_memory(team_name):
    """從數據庫提取球隊記憶，若無則初始化"""
    conn = sqlite3.connect('zeus_ultimate_v92.db')
    c = conn.cursor()
    c.execute("SELECT elo, attack, defense, form FROM team_power WHERE team_name=?", (team_name,))
    row = c.fetchone()
    conn.close()
    if row:
        return row[0], row[1], row[2], row[3]
    return 1500.0, 1.0, 1.0, "-----" # 初始 ELO 1500, 標竿攻防 1.0

def train_model_from_result(home_team, away_team, h_goals, a_goals):
    """核心學習函數：從錯誤中成長"""
    h_elo, h_att, h_def, h_form = get_team_memory(home_team)
    a_elo, a_att, a_def, a_form = get_team_memory(away_team)
    
    # 計算勝平負結果
    h_res = 'W' if h_goals > a_goals else ('D' if h_goals == a_goals else 'L')
    a_res = 'L' if h_goals > a_goals else ('D' if h_goals == a_goals else 'W')
    
    # 更新近五場戰績 (Form Index)
    new_h_form = (h_form.replace("-", "") + h_res)[-5:]
    new_a_form = (a_form.replace("-", "") + a_res)[-5:]

    # ELO 演算法更新
    expected_h = 1 / (1 + 10 ** ((a_elo - (h_elo + 50)) / 400)) # 考慮主場優勢 +50
    actual_h = 1 if h_res == 'W' else (0.5 if h_res == 'D' else 0)
    
    k_factor = 25 # 學習速度
    new_h_elo = h_elo + k_factor * (actual_h - expected_h)
    new_a_elo = a_elo + k_factor * ((1 - actual_h) - (1 - expected_h))
    
    # 攻防權重微調 (動態修正 L_h, L_a)
    # 若進球超過預期，提升進攻力；若失球低於預期，提升防禦力
    new_h_att = h_att * 0.95 + (h_goals / 1.4) * 0.05
    new_h_def = h_def * 0.95 + (a_goals / 1.4) * 0.05
    new_a_att = a_att * 0.95 + (a_goals / 1.4) * 0.05
    new_a_def = a_def * 0.95 + (h_goals / 1.4) * 0.05

    conn = sqlite3.connect('zeus_ultimate_v92.db')
    c = conn.cursor()
    c.execute("INSERT OR REPLACE INTO team_power VALUES (?, ?, ?, ?, ?)", 
              (home_team, new_h_elo, new_h_att, new_h_def, new_h_form))
    c.execute("INSERT OR REPLACE INTO team_power VALUES (?, ?, ?, ?, ?)", 
              (away_team, new_a_elo, new_a_att, new_a_def, new_a_form))
    conn.commit()
    conn.close()

# ==========================================
# 🧠 2. 量化分析核心 (HDA + 大小球 + 波膽)
# ==========================================
def power_method_probs(odds):
    """去水演算法：還原莊家心中真實機率"""
    odds_arr = np.array(odds, dtype=float)
    try:
        def func(k): return np.sum(np.power(1/odds_arr, k)) - 1.0
        res = root_scalar(func, bracket=[0.1, 5.0], method='brentq')
        return np.power(1/odds_arr, res.root)
    except:
        return (1/odds_arr) / np.sum(1/odds_arr)

def run_deep_quant(h_o, d_o, a_o, o25_o, u25_o, home_team, away_team):
    # 1. 取得去水後的市場預期
    p_h_mkt, p_d_mkt, p_a_mkt = power_method_probs([h_o, d_o, a_o])
    p_u25_mkt = power_method_probs([o25_o, u25_o])[1] if (o25_o and u25_o) else 0.5
    
    # 2. 注入數據庫球隊記憶 (基本面修正)
    h_elo, h_att, h_def, h_form = get_team_memory(home_team)
    a_elo, a_att, a_def, a_form = get_team_memory(away_team)
    
    # 3. 反推預期進球 $L_h, L_a$
    try: 
        total_lambda = root_scalar(lambda x: poisson.cdf(2, x) - p_u25_mkt, bracket=[0.1, 10.0]).root
    except: 
        total_lambda = 2.7
    
    # 結合戰力比與攻防數據修正權重
    power_ratio = (p_h_mkt / p_a_mkt) * (h_att / a_def) * (a_att / h_def)
    l_h = total_lambda * (power_ratio**0.7 / (power_ratio**0.7 + 1))
    l_a = total_lambda - l_h
    
    # 4. 生成波膽矩陣 (完美考慮和局 Dixon-Coles 修正)
    max_g = 6
    matrix = np.outer(poisson.pmf(np.arange(max_g), l_h), poisson.pmf(np.arange(max_g), l_a))
    
    # Dixon-Coles 修正低比分和局機率 (修正平手偏差)
    rho = -0.08
    matrix[0,0] *= (1 - l_h*l_a*rho)
    matrix[0,1] *= (1 + l_h*rho)
    matrix[1,0] *= (1 + l_a*rho)
    matrix[1,1] *= (1 - rho)
    matrix /= matrix.sum()
    
    # 5. 計算各項指標
    prob_h = np.sum(np.tril(matrix, -1))
    prob_d = np.sum(np.diag(matrix))
    prob_a = np.sum(np.triu(matrix, 1))
    prob_o25 = 1 - np.sum([matrix[i, j] for i in range(3) for j in range(3-i)])
    
    # 6. 凱利準則建議
    def get_rec(label, p, o):
        edge = p - (1/o)
        return edge, label, o

    options = [
        get_rec("🏠 主勝", prob_h, h_o),
        get_rec("🤝 和局", prob_d, d_o),
        get_rec("🚀 客勝", prob_a, a_o),
        get_rec("⚽ 大 2.5", prob_o25, o25_o),
        get_rec("🛡️ 小 2.5", 1-prob_o25, u25_o)
    ]
    best_edge, best_label, best_odds = max(options, key=lambda x: x[0])
    
    rec_text = f"{best_label} (賠率 {best_odds})"
    confidence = "⭐⭐⭐⭐⭐" if best_edge > 0.05 else ("⭐⭐⭐" if best_edge > 0.02 else "⭐")
    
    top_scores = {f"{r}:{c}": matrix[r, c] for r, c in zip(*np.unravel_index(np.argsort(matrix, axis=None)[::-1][:3], matrix.shape))}
    
    return prob_h, prob_d, prob_a, prob_o25, f"🎯 建議玩法：{rec_text} | 優勢: {best_edge:+.1%} | 信心: {confidence}", top_scores, total_lambda, h_form, a_form

# ==========================================
# 🖥️ 3. 介面優化與搜尋功能
# ==========================================
def main():
    st.set_page_config(page_title="ZEUS QUANT ULTIMATE", layout="wide")
    tw_tz = pytz.timezone('Asia/Taipei')
    
    st.markdown("""
        <style>
        .stApp { background-color: #0b0f19; color: #e2e8f0; }
        .form-badge { padding: 3px 10px; border-radius: 6px; margin-right: 5px; font-weight: bold; font-family: 'Courier New'; }
        .form-W { background-color: #10b981; color: #fff; }
        .form-D { background-color: #f59e0b; color: #fff; }
        .form-L { background-color: #ef4444; color: #fff; }
        .form-NEW { background-color: #475569; color: #cbd5e1; border: 1px dashed; }
        .rec-box { border-left: 5px solid #38bdf8; background: #1e293b; padding: 15px; border-radius: 0 8px 8px 0; margin: 10px 0; }
        </style>
    """, unsafe_allow_html=True)

    st.title("⚛️ ZEUS QUANT ULTIMATE v92.0")
    
    api_key = st.secrets.get("ODDS_API_KEY", "YOUR_KEY_HERE")
    
    tab_predict, tab_train = st.tabs(["🎯 即時量化預測", "🧠 模型覆盤與學習"])

    with tab_predict:
        # 強化的搜尋欄：移除前後空格、不分大小寫
        query = st.text_input("🔍 搜尋球隊、聯賽或國家 (例: Arsenal, Premier, 瑞典超)", "").strip().lower()
        
        url = f"https://api.the-odds-api.com/v4/sports/soccer/odds/?apiKey={api_key}&regions=eu&markets=h2h,totals"
        try:
            res = requests.get(url)
            data = res.json()
        except:
            st.error("API 請求失敗，請檢查網路或金鑰。")
            return

        st.caption(f"數據同步時間: {datetime.now(tw_tz).strftime('%Y-%m-%d %H:%M:%S')}")

        for m in data:
            home, away, league = m['home_team'], m['away_team'], m['sport_title']
            
            # 全域模糊比對：搜尋範圍包含主隊、客隊、聯賽名稱
            if query and (query not in home.lower() and query not in away.lower() and query not in league.lower()):
                continue

            try:
                # 盤口解析
                bms = m['bookmakers'][0]['markets']
                h2h = next(mk for mk in bms if mk['key'] == 'h2h')
                totals = next((mk for mk in bms if mk['key'] == 'totals'), None)
                
                h_o = next(o['price'] for o in h2h['outcomes'] if o['name'] == home)
                d_o = next(o['price'] for o in h2h['outcomes'] if o['name'] == 'Draw')
                a_o = next(o['price'] for o in h2h['outcomes'] if o['name'] == away)
                o25_o = next((o['price'] for o in totals['outcomes'] if o['name'] == 'Over'), 1.9) if totals else 1.9
                u25_o = next((o['price'] for o in totals['outcomes'] if o['name'] == 'Under'), 1.9) if totals else 1.9

                # 執行分析
                ph, pd, pa, po25, advice, scores, t_lambda, h_form, a_form = run_deep_quant(h_o, d_o, a_o, o25_o, u25_o, home, away)
                
                # 詳細分析摺疊面板
                with st.expander(f"🏆 {league} | {home} vs {away} | 預期進球: {t_lambda:.2f}"):
                    st.markdown(f"<div class='rec-box'>{advice}</div>", unsafe_allow_html=True)
                    
                    c1, c2 = st.columns(2)
                    with c1:
                        st.markdown("#### 📊 機率分佈 (含和局)")
                        st.write(f"🏠 主勝: `{ph:.1%}` | 🤝 和局: `{pd:.1%}` | 🚀 客勝: `{pa:.1%}`")
                        st.write(f"⚽ 大 2.5: `{po25:.1%}` | 🛡️ 小 2.5: `{1-po25:.1%}`")
                        st.markdown("**🎯 波膽推薦：**")
                        for s, p in scores.items():
                            st.markdown(f"`{s}` 發生率: **{p:.1%}**")
                    
                    with c2:
                        st.markdown("#### 📚 數據庫記憶 (近期戰績)")
                        def get_form_html(f):
                            if f == "-----": return "<span class='form-badge form-NEW'>🆕 新數據</span>"
                            return "".join([f"<span class='form-badge form-{char}'>{char}</span>" for char in f])
                        
                        st.markdown(f"**{home}** (主): {get_form_html(h_form)}", unsafe_allow_html=True)
                        st.markdown(f"**{away}** (客): {get_form_html(a_form)}", unsafe_allow_html=True)
                        st.caption("戰績標籤需在『模型覆盤』輸入賽果後自動生成。")
                
                # 自動記錄未結算賽事
                start_time = datetime.strptime(m['commence_time'], "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=pytz.utc).astimezone(tw_tz)
                conn = sqlite3.connect('zeus_ultimate_v92.db')
                conn.execute("INSERT OR IGNORE INTO matches VALUES (?,?,?,?,?,?,?,?,?)", 
                             (f"{m['id']}", league, home, away, advice, "", "待定", datetime.now(tw_tz).strftime('%m/%d %H:%M'), start_time.strftime('%m/%d %H:%M')))
                conn.commit(); conn.close()

            except Exception:
                continue

    with tab_train:
        st.header("🧠 歷史覆盤與進化中心")
        st.info("💡 操作說明：在這裡輸入比賽的真實比分（例 3:1）。系統會根據比分修正球隊的進攻係數、防禦係數以及 ELO 分數。這就是讓模型「從錯誤中成長」的核心。")
        
        conn = sqlite3.connect('zeus_ultimate_v92.db')
        df = pd.read_sql_query("SELECT match_id, start_time as '開賽時間', home as '主隊', away as '客隊', result as '填寫真實比分(例1:0)' FROM matches WHERE status='待定' ORDER BY timestamp DESC LIMIT 30", conn)
        
        edited_df = st.data_editor(df, disabled=["match_id", "開賽時間", "主隊", "客隊"], use_container_width=True, hide_index=True)
        
        if st.button("🚀 錄入數據並執行模型進化"):
            c = conn.cursor()
            for _, row in edited_df.iterrows():
                score = row['填寫真實比分(例1:0)']
                if score and ":" in str(score):
                    try:
                        hg, ag = map(int, score.split(":"))
                        c.execute("UPDATE matches SET result=?, status='已結算' WHERE match_id=?", (score, row['match_id']))
                        # 執行球隊記憶更新
                        train_model_from_result(row['主隊'], row['客隊'], hg, ag)
                    except: pass
            conn.commit()
            st.success("✅ 進化成功！球隊戰力與近況已更新。")
        conn.close()

if __name__ == "__main__":
    main()
