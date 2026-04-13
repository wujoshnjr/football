import streamlit as st
import pandas as pd
import requests
from bs4 import BeautifulSoup
import pytz
import io
import random
from datetime import datetime, timedelta
from football.engine import FootballTradingEngine

# 1. 頁面核心配置
st.set_page_config(page_title="Hedge Fund V5 Ultra", layout="wide", initial_sidebar_state="expanded")
engine = FootballTradingEngine()
tz = pytz.timezone("Asia/Taipei")

# 自定義 CSS 讓介面更專業
st.markdown("""
    <style>
    .stMetric { background-color: #f0f2f6; padding: 10px; border-radius: 10px; }
    .main-header { font-size: 2.5rem; color: #1E3A8A; font-weight: bold; }
    </style>
    """, unsafe_allow_html=True)

st.markdown('<p class="main-header">⚽ Football Trading System v5 (Multi-Source)</p>', unsafe_allow_html=True)

# =========================================
# 🛠️ 數據抓取模組
# =========================================

# 方案 A: Football-Data.org (最推薦)
@st.cache_data(ttl=3600)
def fetch_from_football_data():
    key = st.secrets.get("FOOTBALL_DATA_API_KEY")
    if not key: return []
    url = "https://api.football-data.org/v4/matches"
    headers = {'X-Auth-Token': key}
    data = []
    try:
        res = requests.get(url, headers=headers, timeout=10).json()
        for m in res.get('matches', []):
            pred = engine.predict(m['homeTeam']['name'], m['awayTeam']['name'])
            utc_dt = datetime.strptime(m['utcDate'], '%Y-%m-%dT%H:%M:%SZ')
            pred.update({
                'kickoff_tpe': utc_dt.replace(tzinfo=pytz.utc).astimezone(tz),
                'league': m['competition']['name'],
                'source': 'Football-Data.org'
            })
            data.append(pred)
    except: pass
    return data

# 方案 B: RapidAPI (備援)
@st.cache_data(ttl=3600)
def fetch_from_rapidapi():
    key = st.secrets.get("RAPIDAPI_KEY")
    if not key: return []
    url = "https://api-football-v1.p.rapidapi.com/v3/fixtures"
    headers = {"X-RapidAPI-Key": key, "X-RapidAPI-Host": "api-football-v1.p.rapidapi.com"}
    params = {"date": datetime.now().strftime('%Y-%m-%d')}
    data = []
    try:
        res = requests.get(url, headers=headers, params=params, timeout=10).json()
        for f in res.get('response', []):
            pred = engine.predict(f['teams']['home']['name'], f['teams']['away']['name'])
            dt = datetime.fromisoformat(f['fixture']['date'].replace('Z', '+00:00'))
            pred.update({
                'kickoff_tpe': dt.astimezone(tz),
                'league': f['league']['name'],
                'source': 'RapidAPI (API-Football)'
            })
            data.append(pred)
    except: pass
    return data

# 方案 C: Web Scraping (爬蟲模式)
def scrape_from_web():
    url = "https://www.bbc.com/sport/football/scores-fixtures"
    headers = {'User-Agent': 'Mozilla/5.0'}
    data = []
    try:
        res = requests.get(url, headers=headers, timeout=10)
        soup = BeautifulSoup(res.text, 'html.parser')
        # 簡單邏輯抓取 BBC 賽程清單 (結構可能隨時間變動)
        blocks = soup.select('.gs-u-pb\+')
        for b in blocks[:15]:
            h = b.select_one('.sp-c-fixture__team--home').text.strip()
            a = b.select_one('.sp-c-fixture__team--away').text.strip()
            pred = engine.predict(h, a)
            pred.update({'kickoff_tpe': datetime.now(tz), 'league': 'Live Feed', 'source': 'Web Scraper'})
            data.append(pred)
    except: pass
    return data

# =========================================
# 📊 介面與控制列
# =========================================
st.sidebar.header("📡 數據源切換")
source_choice = st.sidebar.radio(
    "選擇即時數據來源", 
    ["Football-Data (首選)", "RapidAPI (備援)", "Web Scraper (爬蟲)"]
)

if source_choice == "Football-Data (首選)":
    live_matches = fetch_from_football_data()
elif source_choice == "RapidAPI (備援)":
    live_matches = fetch_from_rapidapi()
else:
    with st.spinner("🕷️ 正在解析網頁數據..."):
        live_matches = scrape_from_web()

# 如果所有來源都失敗，啟動 Demo 模式避免白屏
if not live_matches:
    st.sidebar.warning("⚠️ 無法獲取即時賽事，切換至展示模式")
    demo_teams = [("Man City", "Real Madrid", "Champions League"), ("Arsenal", "Liverpool", "Premier League")]
    live_matches = []
    for h, a, l in demo_teams:
        p = engine.predict(h, a)
        p.update({'kickoff_tpe': datetime.now(tz), 'league': l, 'source': 'Demo'})
        live_matches.append(p)

# =========================================
# 🏟️ 預測顯示面板
# =========================================
st.sidebar.divider()
st.sidebar.write(f"🟢 **數據來源:** {live_matches[0]['source'] if live_matches else 'N/A'}")
st.sidebar.write(f"⏰ **同步時間:** {datetime.now(tz).strftime('%H:%M:%S')}")

# 下載按鈕
if live_matches:
    df = pd.DataFrame(live_matches).copy()
    df['kickoff_tpe'] = df['kickoff_tpe'].apply(lambda x: x.strftime('%Y-%m-%d %H:%M'))
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
        df.to_excel(writer, index=False)
    st.sidebar.download_button("📥 匯出今日預測報表", output.getvalue(), "Trading_Report.xlsx")

# 主畫面循環
for res in live_matches:
    with st.expander(f"⚽ {res['league']}: {res['home_team']} vs {res['away_team']}", expanded=True):
        c1, c2, c3 = st.columns([2, 1, 1])
        
        with c1:
            st.markdown(f"#### {res['home_team']} vs {res['away_team']}")
            st.caption(f"📅 開賽: {res['kickoff_tpe'].strftime('%m/%d %H:%M')} (TPE)")
            st.caption(f"📍 數據源: {res['source']}")
            
        with c2:
            st.write("**勝平負機率**")
            st.metric("主勝", f"{res['home_prob']:.1%}")
            st.metric("客勝", f"{res['away_prob']:.1%}")
            
        with c3:
            st.write("**進球預測**")
            st.metric("大 2.5 球", f"{res['over25']:.1%}")
            st.success(f"🎯 推薦比分: {res['top_scores'][0][0]}")

st.divider()
st.caption("Football Trading System v5.0 | 此數據僅供策略研究使用，不構成投資建議。")
