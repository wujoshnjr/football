import streamlit as st
import requests
import math
import pandas as pd
import sqlite3
from datetime import datetime

# ==========================================
# 🛑 極致修復與介面定義
# ==========================================
DB_NAME = "zeus_v900.db"

def init_db():
    conn = sqlite3.connect(DB_NAME, check_same_thread=False)
    conn.execute('''CREATE TABLE IF NOT EXISTS matches 
                    (m_id TEXT PRIMARY KEY, league TEXT, home TEXT, away TEXT, 
                     ph REAL, pd REAL, pa REAL, ho REAL, update_time TEXT)''')
    conn.commit()
    return conn

# 🏆 Winner12 科技風 CSS 注入
def inject_winner12_ui():
    st.markdown("""
    <style>
    .stApp { background-color: #0D1117; color: #C9D1D9; }
    .card {
        background: #161B22; border: 1px solid #30363D;
        border-radius: 12px; padding: 20px; margin-bottom: 15px;
    }
    .metric-grid { display: flex; justify-content: space-around; margin: 15px 0; }
    .metric-item { text-align: center; }
    .prob-val { font-size: 24px; font-weight: 800; color: #58A6FF; }
    .label { font-size: 12px; color: #8B949E; }
    .winner-tag { 
        background: #238636; color: white; padding: 2px 10px; 
        border-radius: 20px; font-size: 12px; font-weight: bold;
    }
    </style>
    """, unsafe_allow_html=True)

# 🧠 純 Python 數學引擎 (徹底捨棄 scipy)
def poisson_prob(k, mu):
    return (mu**k * math.exp(-mu)) / math.factorial(k) if mu > 0 else (1.0 if k==0 else 0.0)

def calculate_probs(ho, do, ao, t_lambda):
    inv = (1/ho) + (1/do) + (1/ao)
    # 🛑 歸一化與防溢出處理
    mh, ma = (1/ho)/inv, (1/ao)/inv
    lh, la = t_lambda * (mh/(mh+ma)), t_lambda * (ma/(mh+ma))
    
    matrix = [[poisson_prob(i, lh) * poisson_prob(j, la) for j in range(6)] for i in range(6)]
    ph = sum(matrix[i][j] for i in range(6) for j in range(i))
    pd = sum(matrix[i][i] for i in range(6))
    pa = sum(matrix[i][j] for j in range(6) for i in range(j))
    
    # 強制機率總和為 1.0 (防止 100% + 100% 錯誤)
    s = ph + pd + pa
    return ph/s, pd/s, pa/s

def main():
    st.set_page_config(page_title="ZEUS v900", layout="wide")
    inject_winner12_ui()
    conn = init_db()
    
    st.markdown("<h1 style='color:#58A6FF;'>⚛️ ZEUS QUANT v900</h1>", unsafe_allow_html=True)
    
    api_key = st.secrets.get("ODDS_API_KEY", "")
    if not api_key:
        st.error("❌ 錯誤 401: 找不到 API 金鑰。請在 Secrets 設定 ODDS_API_KEY。")
        return

    # API 請求與防禦性解析
    url = f"https://api.the-odds-api.com/v4/sports/soccer/odds/?apiKey={api_key}&regions=eu&markets=h2h"
    try:
        res = requests.get(url)
        if res.status_code == 401:
            st.error("❌ API 金鑰無效 (Unauthorized)。")
            return
        matches = res.json()
        
        for m in matches:
            home, away = m['home_team'], m['away_team']
            h2h = m['bookmakers'][0]['markets'][0]['outcomes']
            ho = next(o['price'] for o in h2h if o['name'] == home)
            do = next(o['price'] for o in h2h if o['name'] == 'Draw')
            ao = next(o['price'] for o in h2h if o['name'] == away)
            
            ph, pd, pa = calculate_probs(ho, do, ao, 2.65)
            
            # 🏆 渲染 Winner12 風格卡片
            st.markdown(f"""
            <div class="card">
                <div style="display:flex; justify-content:space-between;">
                    <span style="color:#8B949E;">⚽ {m['sport_title']}</span>
                    <span class="winner-tag">LIVE ANALYZING</span>
                </div>
                <h3 style="margin:10px 0;">{home} <span style="color:#58A6FF;">VS</span> {away}</h3>
                <div class="metric-grid">
                    <div class="metric-item"><div class="label">🏠 主勝機率</div><div class="prob-val">{ph:.1%}</div></div>
                    <div class="metric-item"><div class="label">🤝 和局機率</div><div class="prob-val">{pd:.1%}</div></div>
                    <div class="metric-item"><div class="label">🚀 客勝機率</div><div class="prob-val">{pa:.1%}</div></div>
                </div>
                <div style="font-size:13px; color:#8B949E; border-top:1px solid #30363D; padding-top:10px;">
                    🎯 建議：{"🔥 強烈主勝" if ph > 0.5 else "⚖️ 數據持平"} | 凱利分注建議: {max(0, (ph*ho-1)/(ho-1)*0.1):.1%}
                </div>
            </div>
            """, unsafe_allow_html=True)
            
    except Exception as e:
        st.warning(f"等待數據接入或發生異常: {e}")

if __name__ == "__main__":
    main()
