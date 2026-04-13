import streamlit as st
import pandas as pd
import requests
from bs4 import BeautifulSoup
import pytz
import io
import random
from datetime import datetime, timedelta
from football.engine import FootballTradingEngine

# 1. 系統初始化
st.set_page_config(page_title="Hedge Fund V5 Ultra", layout="wide")
engine = FootballTradingEngine()
tz = pytz.timezone("Asia/Taipei")

# 介面美化
st.markdown("""
    <style>
    .match-card { background-color: #ffffff; border: 1px solid #e0e0e0; padding: 15px; border-radius: 12px; margin-bottom: 10px; box-shadow: 2px 2px 5px rgba(0,0,0,0.05); }
    .stMetric { background-color: #f8f9fa; padding: 10px; border-radius: 8px; }
    </style>
    """, unsafe_allow_html=True)

st.title("⚽ Football Trading System v5 (Ultimate)")

# =========================================
# 📡 數據抓取模組 (API & 爬蟲)
# =========================================

# A. Football-Data.org
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
            h, a = m['homeTeam']['name'], m['awayTeam']['name']
            pred = engine.predict(h, a)
            utc_dt = datetime.strptime(m['utcDate'], '%Y-%m-%dT%H:%M:%SZ')
            pred.update({'kickoff': utc_dt.replace(tzinfo=pytz.utc).astimezone(tz), 'league': m['competition']['name'], 'source': 'Football-Data API'})
            data.append(pred)
    except: pass
    return data

# B. RapidAPI (API-Football)
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
            h, a = f['teams']['home']['name'], f['teams']['away']['name']
            pred = engine.predict(h, a)
            dt = datetime.fromisoformat(f['fixture']['date'].replace('Z', '+00:00'))
            pred.update({'kickoff': dt.astimezone(tz), 'league': f['league']['name'], 'source': 'RapidAPI'})
            data.append(pred)
    except: pass
    return data

# C. Web Scraper (BBC Sport) - 這是最穩定的真實賽事備援
def scrape_real_matches():
    url = "https://www.bbc.com/sport/football/scores-fixtures"
    headers = {'User-Agent': 'Mozilla/5.0'}
    data = []
    try:
        res = requests.get(url, headers=headers, timeout=10)
        soup = BeautifulSoup(res.text, 'lxml')
        # 抓取所有包含比賽名稱的標籤
        match_blocks = soup.find_all('article', class_='sp-c-fixture')
        for b in match_blocks[:15]:
            try:
                teams = b.find_all('span', class_='gs-u-display-none')
                if len(teams) >= 2:
                    h, a = teams[0].text.strip(), teams[1].text.strip()
                    pred = engine.predict(h, a)
                    pred.update({'kickoff': datetime.now(tz), 'league': 'BBC Live Feed', 'source': 'Web Scraper'})
                    data.append(pred)
            except: continue
    except: pass
    return data

# =========================================
# 📊 介面邏輯
# =========================================
st.sidebar.header("📡 數據管理中心")
source_mode = st.sidebar.radio("選擇數據來源", ["Football-Data (API)", "RapidAPI (API)", "爬蟲模式 (BBC Sport)"])

if source_mode == "Football-Data (API)":
    live_matches = fetch_football_data()
elif source_mode == "RapidAPI (API)":
    live_matches = fetch_rapid_api()
else:
    with st.spinner("🕷️ 正在爬取即時網頁賽程..."):
        live_matches = scrape_real_matches()

# 萬一真的沒資料，跑 Demo
if not live_matches:
    st.sidebar.warning("當前無即時賽事，載入展示數據")
    for h, a, l in [("Liverpool", "Arsenal", "Premier League"), ("Man City", "Real Madrid", "UCL")]:
        p = engine.predict(h, a)
        p.update({'kickoff': datetime.now(tz), 'league': l, 'source': 'Demo Mode'})
        live_matches.append(p)

# 下載按鈕
df = pd.DataFrame(live_matches).copy()
df['kickoff'] = df['kickoff'].apply(lambda x: x.strftime('%H:%M'))
output = io.BytesIO()
with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
    df.to_excel(writer, index=False)
st.sidebar.download_button("📥 導出預測報表", output.getvalue(), "Trading_Report.xlsx")

# =========================================
# 🏟️ 顯示面板
# =========================================
st.subheader(f"📊 偵測到賽事: {len(live_matches)} 場 (來源: {live_matches[0]['source']})")

for res in live_matches:
    st.markdown(f"""
    <div class="match-card">
        <div style="display: flex; justify-content: space-between;">
            <span style="font-weight: bold; color: #1E3A8A;">🏆 {res['league']}</span>
            <span style="color: #666;">⏰ {res['kickoff'].strftime('%m/%d %H:%M')}</span>
        </div>
        <hr style="margin: 10px 0;">
        <div style="text-align: center; font-size: 1.2rem; font-weight: bold; margin-bottom: 15px;">
            {res['home_team']} <span style="color: #e63946;">vs</span> {res['away_team']}
        </div>
    </div>
    """, unsafe_allow_html=True)
    
    c1, c2, c3 = st.columns(3)
    with c1:
        st.metric("主勝機率", f"{res['home_prob']:.1%}")
    with c2:
        st.metric("客勝機率", f"{res['away_prob']:.1%}")
    with c3:
        st.metric("大 2.5 球", f"{res['over25']:.1%}")
        st.write(f"🎯 推薦比分: **{res['top_scores'][0][0]}**")
    st.divider()

st.sidebar.write(f"✅ 系統狀態: 運作中")
st.sidebar.write(f"🔄 最後同步: {datetime.now(tz).strftime('%H:%M:%S')}")
