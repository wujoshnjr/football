import streamlit as st
import pandas as pd
import requests
from bs4 import BeautifulSoup
import pytz
import io
import time
from datetime import datetime
from football.engine import FootballTradingEngine

# 1. 核心頁面配置
st.set_page_config(
    page_title="Hedge Fund Alpha V5",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="expanded"
)

# 初始化模型與時區
engine = FootballTradingEngine()
tz = pytz.timezone("Asia/Taipei")

# 2. 進階自定義 CSS (更精緻的 UI)
st.markdown("""
    <style>
    .match-card {
        border-radius: 15px;
        padding: 20px;
        background-color: #ffffff;
        border: 1px solid #e9ecef;
        box-shadow: 0 4px 6px rgba(0,0,0,0.05);
        margin-bottom: 20px;
    }
    .status-live { color: #d9534f; font-weight: bold; animation: blinker 1.5s linear infinite; }
    @keyframes blinker { 50% { opacity: 0; } }
    .metric-box { text-align: center; background: #f8f9fa; border-radius: 8px; padding: 10px; }
    </style>
    """, unsafe_allow_html=True)

# =========================================
# 📡 強化版數據抓取 (增加對抗限速機制)
# =========================================

@st.cache_data(ttl=600)
def fetch_data_hub(source_type):
    data = []
    
    # --- 來源 A: Football-Data.org ---
    if source_type == "Football-Data (首選)":
        key = st.secrets.get("FOOTBALL_DATA_API_KEY")
        if not key: return []
        headers = {'X-Auth-Token': key}
        try:
            res = requests.get("https://api.football-data.org/v4/matches", headers=headers, timeout=12).json()
            for m in res.get('matches', []):
                h_name = m['homeTeam']['shortName'] or m['homeTeam']['name']
                a_name = m['awayTeam']['shortName'] or m['awayTeam']['name']
                pred = engine.predict(h_name, a_name)
                utc_dt = datetime.strptime(m['utcDate'], '%Y-%m-%dT%H:%M:%SZ')
                pred.update({
                    'kickoff': utc_dt.replace(tzinfo=pytz.utc).astimezone(tz),
                    'league': f"🏆 {m['competition']['name']}",
                    'source': 'Verified API'
                })
                data.append(pred)
        except: pass

    # --- 來源 B: Web Scraper (高效能解析) ---
    elif source_type == "爬蟲模式":
        url = "https://www.bbc.com/sport/football/scores-fixtures"
        headers = {'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36'}
        try:
            res = requests.get(url, headers=headers, timeout=10)
            soup = BeautifulSoup(res.text, 'html.parser')
            for b in soup.select('.gs-u-pb\+')[:12]:
                h = b.select_one('.sp-c-fixture__team--home').text.strip()
                a = b.select_one('.sp-c-fixture__team--away').text.strip()
                pred = engine.predict(h, a)
                pred.update({'kickoff': datetime.now(tz), 'league': '📡 Live Stream', 'source': 'Web Scraper'})
                data.append(pred)
        except: pass
    
    return data

# =========================================
# 📊 側邊欄控制與分析工具
# =========================================
with st.sidebar:
    st.image("https://cdn-icons-png.flaticon.com/512/907/907690.png", width=80)
    st.title("數據管理中心")
    
    source = st.radio("📡 選擇即時賽事來源", ["Football-Data (首選)", "RapidAPI (備援)", "爬蟲模式"])
    
    st.divider()
    st.write("⚙️ **分析偏好**")
    threshold = st.slider("勝率預警門檻 (%)", 40, 80, 55)
    
    # 導出 Excel 功能
    st.divider()
    st.write("📅 **最後同步:**", datetime.now(tz).strftime('%H:%M:%S'))

# =========================================
# 🏟️ 主畫面渲染
# =========================================
