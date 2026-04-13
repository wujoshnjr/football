import streamlit as st
import pandas as pd
import requests
import pytz
import io
from datetime import datetime, timedelta
from football.engine import FootballTradingEngine

st.set_page_config(page_title="Hedge Fund V5 - Live Data", layout="wide")
engine = FootballTradingEngine()
tz = pytz.timezone("Asia/Taipei")

# --- API 抓取函式庫 ---
def fetch_real_fixtures():
    """從 Sportmonks 獲取真實賽程"""
    api_token = st.secrets["SPORTMONKS_API_KEY"]
    # 抓取未來 24 小時內的賽程 (範例 URL，需依版本調整)
    url = f"https://api.sportmonks.com/v3/football/fixtures?api_token={api_token}&include=participants;league"
    response = requests.get(url).json()
    return response.get('data', [])

def fetch_live_odds():
    """從 The Odds API 獲取即時賠率"""
    api_key = st.secrets["ODDS_API_KEY"]
    url = f"https://api.the-odds-api.com/v4/sports/soccer_uefa_champs_league/odds/?apiKey={api_key}&regions=eu"
    response = requests.get(url).json()
    return {f"{m['home_team']} vs {m['away_team']}": m['bookmakers'][0]['markets'][0]['outcomes'] for m in response if 'bookmakers' in m}

def fetch_football_news(query):
    """從 News API 獲取相關新聞"""
    api_key = st.secrets["NEWS_API_KEY"]
    url = f"https://newsapi.org/v2/everything?q={query}&language=en&pageSize=3&apiKey={api_key}"
    response = requests.get(url).json()
    return response.get('articles', [])

# --- 全自動流水線 ---
@st.cache_data(ttl=1800) # 每 30 分鐘更新一次真實數據
def run_live_pipeline():
    fixtures = fetch_real_fixtures()
    odds_data = fetch_live_odds()
    
    final_results = []
    for f in fixtures[:10]: # 處理前 10 場
        home = f['participants'][0]['name']
        away = f['participants'][1]['name']
        
        # 執行引擎預測
        res = engine.predict(home, away)
        
        # 處理時間
        res['kickoff_tpe'] = datetime.strptime(f['starting_at'], '%Y-%m-%d %H:%M:%S').replace(tzinfo=pytz.utc).astimezone(tz)
        
        # 匹配賠率數據
        match_key = f"{home} vs {away}"
        res['market_odds'] = odds_data.get(match_key, "N/A")
        
        # 抓取新聞 (選取主隊新聞作為參考)
        res['news'] = fetch_football_news(home)
        
        final_results.append(res)
    return final_results

# 執行自動化抓取
with st.spinner("正在串接 API 數據..."):
    live_data = run_live_pipeline()

# --- UI 顯示 (對沖基金風格) ---
st.title("⚽ Football Trading System v5 (Live Data)")

for res in live_data:
    with st.container():
        col1, col2, col3 = st.columns([2, 1, 1])
        
        with col1:
            st.subheader(f"🏟️ {res['home_team']} vs {res['away_team']}")
            st.caption(f"📅 台北時間: {res['kickoff_tpe'].strftime('%m-%d %H:%M')}")
            
            # 顯示新聞
            with st.expander("📰 相關新聞分析"):
                for art in res['news']:
                    st.write(f"- [{art['title']}]({art['url']})")

        with col2:
            st.write("**Model Prediction**")
            st.metric("Home Win", f"{res['home_prob']:.1%}")
            st.metric("Away Win", f"{res['away_prob']:.1%}")

        with col3:
            st.write("**Market Odds (Live)**")
            if res['market_odds'] != "N/A":
                for outcome in res['market_odds']:
                    st.write(f"{outcome['name']}: {outcome['price']}")
            else:
                st.write("暫無賠率數據")

        st.divider()

# --- Excel 導出邏輯 ---
# (與之前版本相同，處理時區後下載)
