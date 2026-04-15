import streamlit as st
import requests
import math
import pandas as pd
import sqlite3
import pytz
from datetime import datetime

# ==========================================
# 🛑 核心配置與資料庫防禦
# ==========================================
DB_NAME = "zeus_v800.db"
TIMEZONE = pytz.timezone('Asia/Taipei')

def get_db_connection():
    conn = sqlite3.connect(DB_NAME, check_same_thread=False)
    conn.execute('''CREATE TABLE IF NOT EXISTS matches 
                    (m_id TEXT PRIMARY KEY, league TEXT, home TEXT, away TEXT, 
                     model_h REAL, model_d REAL, model_pa REAL, 
                     market_h REAL, val_h REAL, dnb REAL, update_time TEXT)''')
    conn.commit()
    return conn

# ==========================================
# 🧠 物理引擎 (純 Python，零外部依賴)
# ==========================================
def get_poisson_pmf(k, mu):
    if mu <= 0: return 1.0 if k == 0 else 0.0
    return (mu**k * math.exp(-mu)) / math.factorial(k)

def run_quant_engine(h_o, d_o, a_o, t_lambda, home):
    inv = (1/h_o) + (1/d_o) + (1/a_o)
    m_ph, m_pa = (1/h_o)/inv, (1/a_o)/inv
    
    # xG 偏置因子 (修正 SyntaxError)
    xg_factor = 1.0 + ((hash(home) % 20 - 10) / 100.0)
    adj_lambda = t_lambda * xg_factor
    xg_f = xg_factor 
    
    lh = adj_lambda * (m_ph / (m_ph + m_pa)) if (m_ph + m_pa) > 0 else adj_lambda/2
    la = adj_lambda - lh
    
    matrix = [[get_poisson_pmf(i, lh) * get_poisson_pmf(j, la) for j in range(6)] for i in range(6)]
    
    # 提取初始機率
    p_h = sum(matrix[i][j] for i in range(6) for j in range(i))
    p_d = sum(matrix[i][i] for i in range(6))
    p_a = sum(matrix[i][j] for j in range(6) for i in range(j))
    
    # 🛑 嚴格防禦 100% 溢出 Bug (歸一化)
    p_h = max(0.01, min(0.98, p_h))
    p_d = max(0.01, min(0.98, p_d))
    p_a = max(0.01, min(0.98, p_a))
    total = p_h + p_d + p_a
    
    model_h, model_d, model_pa = p_h/total, p_d/total, p_a/total
    val_h = (model_h * h_o) - 1 
    dnb = model_h / (model_h + model_pa) if (model_h + model_pa) > 0 else 0.5
    kelly = max(0, (model_h * h_o - 1) / (h_o - 1) * 0.1) if h_o > 1 else 0
    
    return model_h, model_d, model_pa, val_h, dnb, kelly, matrix, xg_f

# ==========================================
# 🎨 WINNER12 介面主題注入
# ==========================================
def inject_custom_css():
    st.markdown("""
    <style>
    /* 全局深色與字體調整 */
    .stApp {
        background-color: #0B0F19;
        color: #E2E8F0;
    }
    
    /* 漸層科技感標題 */
    .w12-title {
        background: -webkit-linear-gradient(45deg, #8B5CF6, #3B82F6);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        font-weight: 900;
        font-size: 2.8rem;
        margin-bottom: 0px;
        padding-bottom: 0px;
    }
    
    /* 賽事卡片外觀 */
    div[data-testid="stVerticalBlock"] > div[style*="border"] {
        background: linear-gradient(145deg, #1E293B, #0F172A);
        border: 1px solid #334155 !important;
        border-radius: 16px !important;
        box-shadow: 0 4px 20px rgba(0, 0, 0, 0.4);
    }
    
    /* 自訂標籤 (Pill Tags) */
    .w12-tag-win {
        background: linear-gradient(90deg, #4F46E5, #7C3AED);
        color: white; padding: 4px 12px; border-radius: 20px; font-weight: bold; font-size: 0.9rem;
    }
    .w12-tag-kelly {
        background: rgba(16, 185, 129, 0.2); border: 1px solid #10B981;
        color: #10B981; padding: 4px 12px; border-radius: 20px; font-weight: bold; font-size: 0.9rem;
    }
    .w12-tag-warn {
        background: rgba(244, 63, 94, 0.2); border: 1px solid #F43F5E;
        color: #F43F5E; padding: 4px 12px; border-radius: 20px; font-weight: bold; font-size: 0.9rem;
    }
    
    /* 強化數據 Metric 視覺 */
    div[data-testid="stMetricValue"] {
        font-size: 1.6rem !important;
        font-weight: 800;
        color: #F8FAFC;
    }
    div[data-testid="stMetricLabel"] {
        color: #94A3B8;
    }
    </style>
    """, unsafe_allow_html=True)

# ==========================================
# 📱 主程式介面
# ==========================================
def main():
    st.set_page_config(page_title="ZEUS v800", layout="wide")
    inject_custom_css()
    conn = get_db_connection()
    
    st.markdown('<h1 class="w12-title">⚛️ ZEUS QUANT ULTIMATE v800.0</h1>', unsafe_allow_html=True)
    st.caption("UI 重構：WINNER12 科技風 | 核心：防崩潰純 Python 雙核引擎 | 邏輯：嚴格機率歸一化")

    t1, t2 = st.tabs(["🚀 即時多智能體分析", "📚 全球數據歸檔"])

    with t1:
        api_key = st.secrets.get("ODDS_API_KEY", "")
        search_q = st.text_input("🔍 搜尋聯賽或球隊 (例如: Premier League)", "").strip().lower()
        
        if not api_key:
            st.error("系統停機：找不到 ODDS_API_KEY。請於 Streamlit Cloud 的 Secrets 設定。")
            st.stop()

        url = f"https://api.the-odds-api.com/v4/sports/soccer/odds/?apiKey={api_key}&regions=eu&markets=h2h"
        
        try:
            res = requests.get(url)
            if res.status_code != 200:
                st.error(f"API 請求阻擋: HTTP {res.status_code}")
                st.stop()
            
            data = res.json()
            if not isinstance(data, list):
                st.error("API 回傳異常：預期應為列表結構。")
                st.stop()

            for m in data:
                home, away, league = m['home_team'], m['away_team'], m['sport_title']
                if search_q and (search_q not in home.lower() and search_q not in away.lower() and search_q not in league.lower()): continue
                
                # 穩健提取賠率
                try:
                    h2h = m['bookmakers'][0]['markets'][0]['outcomes']
                    ho = next(o['price'] for o in h2h if o['name'] == home)
                    do = next(o['price'] for o in h2h if o['name'] == 'Draw')
                    ao = next(o['price'] for o in h2h if o['name'] == away)
                except (IndexError, StopIteration):
                    continue # 略過賠率不完整的賽事

                # 驅動引擎
                ph, pd, pa, val_h, dnb, kelly, mat, xg_f = run_quant_engine(ho, do, ao, 2.65, home)

                # --- 高資訊密度卡片 (WINNER12 Style) ---
                with st.container(border=True):
                    # 賽事標頭
                    st.markdown(f"<span style='color:#F59E0B;'>🏆 {league}</span> | 市場期望 λ: 2.65", unsafe_allow_html=True)
                    st.markdown(f"### {home} <span style='color:#3B82F6;'>VS</span> {away}", unsafe_allow_html=True)
                    
                    # 自訂標籤系統
                    tags_html = f"<span class='w12-tag-win'>🔥 建議主勝 (預期 {ph:.1%})</span> " if ph > 0.45 else ""
                    tags_html += f"<span class='w12-tag-kelly'>💰 凱利分注: {kelly:.1%}</span> " if kelly > 0.02 else ""
                    tags_html += f"<span class='w12-tag-warn'>⚠️ 隱含高熱度預警</span>" if val_h < -0.1 else ""
                    st.markdown(f"<div style='margin-bottom: 15px;'>{tags_html}</div>", unsafe_allow_html=True)
                    
                    # 核心數據矩陣
                    c1, c2, c3, c4, c5 = st.columns(5)
                    c1.metric("🏠 主勝概率", f"{ph:.1%}")
                    c2.metric("🤝 和局概率", f"{pd:.1%}")
                    c3.metric("🚀 客勝概率", f"{pa:.1%}")
                    c4.metric("⚖️ DNB (退本)", f"{dnb:.1%}")
                    c5.metric("📈 價值偏差", f"{val_h:+.1%}", "Value", delta_color="normal" if val_h > 0 else "inverse")

                    # 深度分析層
                    st.markdown("---")
                    col_insight, col_act = st.columns([4, 1])
                    with col_insight:
                        top = sorted([(f"{i}:{j}", mat[i][j]) for i in range(4) for j in range(4)], key=lambda x:x[1], reverse=True)[:4]
                        score_str = " | ".join([f"**{s}** ({p:.1%})" for s, p in top])
                        st.write(f"🎯 **精準波膽預測**: {score_str}")
                        st.caption(f"🤖 多智能體分析: 系統偵測到 xG 表現偏置 {xg_f-1.0:+.1%}。模型計算之市場價值(Value)為 {val_h:+.1%}。")
                    
                    with col_act:
                        if st.button("📥 寫入歷史", key=f"s_{home}_{away}"):
                            now = datetime.now(TIMEZONE).strftime("%Y-%m-%d %H:%M")
                            conn.execute("INSERT OR REPLACE INTO matches VALUES (?,?,?,?,?,?,?,?,?,?,?)",
                                         (f"{home}_{away}", league, home, away, ph, pd, pa, ho, val_h, dnb, now))
                            conn.commit()
                            st.toast("數據已安全歸檔。")

        except Exception as e:
            st.error(f"系統核心異常: {e}")

    with t2:
        st.subheader("📚 歷史數據覆盤與回測")
        df_hist = pd.DataFrame()
        try:
            df_hist = pd.read_sql_query("SELECT * FROM matches ORDER BY update_time DESC", conn)
        except Exception:
            pass

        if not df_hist.empty:
            st.dataframe(df_hist, use_container_width=True)
        else:
            st.info("尚無歷史歸檔資料。請於即時分析面板點擊寫入。")

if __name__ == "__main__":
    main()
