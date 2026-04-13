import streamlit as st
import pandas as pd
import requests
from bs4 import BeautifulSoup
import pytz
import io
from datetime import datetime, timedelta
from football.engine import FootballTradingEngine

# 1. 初始化
st.set_page_config(page_title="Hedge Fund V5 Ultra", layout="wide")
engine = FootballTradingEngine()
tz = pytz.timezone("Asia/Taipei")

st.markdown("""
    <style>
    .stMetric { background-color: #f8f9fa; padding: 15px; border-radius: 10px; border: 1px solid #e0e0e0; }
    </style>
    """, unsafe_allow_html=True)

st.title("⚽ Football Trading System v5 (Multi-Source)")

# =========================================
# 📡 數據源 A: Football-Data.org
# =========================================
@st.cache_data(ttl=1800)
def fetch_football_data():
    key = st.secrets.get("FOOTBALL_DATA_API_KEY")
    if not key: return []
    url = "https://api.football-data.org/v4/matches"
    headers = {'X-Auth-Token': key}
    data = []
    try:
        res = requests.get(url, headers=headers, timeout=10).json()
        for m in res.get('matches', []):
            home = m['homeTeam']['shortName'] or m['homeTeam']['name']
            away = m['awayTeam']['shortName'] or m['awayTeam']['name']
            pred = engine.predict(home, away)
            utc_dt = datetime.strptime(m['utcDate'], '%Y-%m-%dT%H:%M:%SZ')
            pred.update({
                'kickoff_tpe': utc_dt.replace(tzinfo=pytz.utc).astimezone(tz),
                'league': m['competition']['name'],
                'source': 'Football-Data.org'
            })
            data.append(pred)
    except: pass
    return data

# =========================================
# 📡 數據源 B: RapidAPI (API-Football)
# =========================================
@st.cache_data(ttl=1800)
def fetch_rapid_api():
    key = st.secrets.get("RAPIDAPI_KEY")
    if not key: return []
    url = "https://api-football-v1.p.rapidapi.com/v3/fixtures"
    headers = {"X-RapidAPI-Key": key, "X-RapidAPI-Host": "api-football-v1.p.rapidapi.com"}
    params = {"date": datetime.now().strftime('%Y-%m-%d')}
    data = []
    try:
        res = requests.get(url, headers=headers, params=params, timeout=10).json()
        for f in res.get('response', []):
            home = f['teams']['home']['name']
            away = f['teams']['away']['name']
            pred = engine.predict(home, away)
            dt = datetime.fromisoformat(f['fixture']['date'].replace('Z', '+00:00'))
            pred.update({
                'kickoff_tpe': dt.astimezone(tz),
                'league': f['league']['name'],
                'source': 'RapidAPI'
            })
            data.append(pred)
    except: pass
    return data

# =========================================
# 🕷️ 數據源 C: Web Scraping (爬蟲模式)
# =========================================
def scrape_bbc_data():
    url = "https://www.bbc.com/sport/football/scores-fixtures"
    headers = {'User-Agent': 'Mozilla/5.0'}
    data = []
    try:
        res = requests.get(url, headers=headers, timeout=10)
        soup = BeautifulSoup(res.text, 'html.parser')
        # 爬取 BBC 結構中的比賽塊
        blocks = soup.select('.gs-u-pb\+')
        for b in blocks[:10]:
            home = b.select_one('.sp-c-fixture__team--home').text.strip()
            away = b.select_one('.sp-c-fixture__team--away').text.strip()
            pred = engine.predict(home, away)
            pred.update({
                'kickoff_tpe': datetime.now(tz), 
                'league': 'Live Feed', 
                'source': 'Web Scraper'
            })
            data.append(pred)
    except: pass
    return data

# =========================================
# 📊 邏輯切換與顯示
# =========================================
st.sidebar.header("📊 數據管理中心")
source = st.sidebar.radio("選擇即時賽事來源", ["Football-Data (首選)", "RapidAPI (備用)", "爬蟲模式"])

if source == "Football-Data (首選)":
    live_matches = fetch_football_data()
elif source == "RapidAPI (備用)":
    live_matches = fetch_rapid_api()
else:
    with st.spinner("🕷️ 正在爬取即時數據..."):
        live_matches = scrape_bbc_data()

# 備援：如果全部都沒有比賽，顯示模擬數據
if not live_matches:
    st.sidebar.warning("當前時段無即時賽事，顯示模擬數據")
    demo = [("Man City", "Real Madrid", "Champions League"), ("Arsenal", "Liverpool", "Premier League")]
    for h, a, l in demo:
        p = engine.predict(h, a)
        p.update({'kickoff_tpe': datetime.now(tz), 'league': l, 'source': 'Demo Mode'})
        live_matches.append(p)

# 下載報表功能
if live_matches:
    df = pd.DataFrame(live_matches).copy()
    df['kickoff_tpe'] = df['kickoff_tpe'].apply(lambda x: x.strftime('%H:%M'))
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
        df.to_excel(writer, index=False)
    st.sidebar.download_button("📥 下載分析報表 (Excel)", output.getvalue(), "Trading_Report.xlsx")

# 主畫面渲染
for res in live_matches:
    with st.expander(f"🏟️ {res['league']}: {res['home_team']} vs {res['away_team']}", expanded=True):
        c1, c2, c3 = st.columns([2, 1, 1])
        with c1:
            st.markdown(f"**{res['home_team']} vs {res['away_team']}**")
            st.caption(f"🕒 TPE 時間: {res['kickoff_tpe'].strftime('%m/%d %H:%M')}")
            st.caption(f"📍 數據來源: {res['source']}")
        with c2:
            st.metric("主勝機率", f"{res['home_prob']:.1%}")
            st.metric("客勝機率", f"{res['away_prob']:.1%}")
        with c3:
            st.metric("大 2.5 球", f"{res['over25']:.1%}")
            st.success(f"🎯 推薦: {res['top_scores'][0][0]}")
