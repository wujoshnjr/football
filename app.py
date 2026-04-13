import streamlit as st
import pandas as pd
import requests
import pytz
import io
from datetime import datetime
from football.engine import FootballTradingEngine

# 1. 基礎設定
st.set_page_config(page_title="Football Trading System v5 (Live)", layout="wide")
engine = FootballTradingEngine()
tz = pytz.timezone("Asia/Taipei")

st.title("⚽ Football Trading System v5 (Live Data)")

# =========================================
# 🛠️ 安全讀取 Secrets (防止 KeyError)
# =========================================
SM_KEY = st.secrets.get("SPORTMONKS_API_KEY")
ODDS_KEY = st.secrets.get("ODDS_API_KEY")
NEWS_KEY = st.secrets.get("NEWS_API_KEY")

if not SM_KEY:
    st.error("❌ 偵測不到 SPORTMONKS_API_KEY！請檢查 Streamlit Cloud 的 Settings -> Secrets。")
    st.info("確保格式為：SPORTMONKS_API_KEY = \"你的金鑰\"")
    st.stop()

# =========================================
# 🚀 數據抓取流水線
# =========================================
@st.cache_data(ttl=1800)
def run_live_pipeline():
    # --- A. 抓取真實賽程 (Sportmonks) ---
    sm_url = f"https://api.sportmonks.com/v3/football/fixtures?api_token={SM_KEY}&include=participants;league"
    
    try:
        sm_res = requests.get(sm_url, timeout=10).json()
        raw_fixtures = sm_res.get('data', [])
    except Exception as e:
        st.warning(f"無法從 Sportmonks 取得數據: {e}")
        raw_fixtures = []

    # --- B. 抓取即時賠率 (The Odds API) ---
    odds_lookup = {}
    if ODDS_KEY:
        odds_url = f"https://api.the-odds-api.com/v4/sports/soccer_epl/odds/?apiKey={ODDS_KEY}&regions=eu"
        try:
            odds_res = requests.get(odds_url, timeout=10).json()
            if isinstance(odds_res, list):
                odds_lookup = { (m['home_team'], m['away_team']): m for m in odds_res }
        except:
            pass

    # --- C. 整合與預測 ---
    final_data = []
    for f in raw_fixtures:
        try:
            home = f['participants'][0]['name']
            away = f['participants'][1]['name']
            # 模型預測
            res = engine.predict(home, away)
            # 時間處理 (UTC -> TPE)
            utc_dt = datetime.strptime(f['starting_at'], '%Y-%m-%d %H:%M:%S')
            res['kickoff_tpe'] = utc_dt.replace(tzinfo=pytz.utc).astimezone(tz)
            # 賠率與新聞
            res['market_odds'] = odds_lookup.get((home, away), None)
            
            # 抓取新聞 (News API)
            if NEWS_KEY:
                news_url = f"https://newsapi.org/v2/everything?q={home}&apiKey={NEWS_KEY}&pageSize=1"
                res['news'] = requests.get(news_url, timeout=5).json().get('articles', [])
            else:
                res['news'] = []

            final_data.append(res)
        except:
            continue
            
    return final_data

# 啟動程序
live_matches = run_live_pipeline()

# =========================================
# 📊 側邊欄與報表
# =========================================
st.sidebar.header("📊 系統控制台")
st.sidebar.write(f"最後同步: {datetime.now(tz).strftime('%H:%M:%S')}")

if live_matches:
    # 準備 Excel 數據 (移除時區防止報錯)
    df_excel = pd.DataFrame(live_matches).copy()
    if 'kickoff_tpe' in df_excel.columns:
        df_excel['kickoff_tpe'] = df_excel['kickoff_tpe'].dt.strftime('%Y-%m-%d %H:%M')
    
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
        df_excel.to_excel(writer, index=False, sheet_name='Live_Report')
    
    st.sidebar.download_button(
        label="📥 下載今日真實預測報表",
        data=output.getvalue(),
        file_name=f"Trading_Report_{datetime.now(tz).strftime('%Y%m%d')}.xlsx",
        mime="application/vnd.ms-excel"
    )

# =========================================
# 🏟️ 主面板 (真實比賽)
# =========================================
if not live_matches:
    st.info("🔄 正在等待 API 數據... 若長時間無畫面，請確認您的 API 方案是否支援目前聯賽。")
else:
    for res in live_matches:
        with st.container():
            c1, c2, c3 = st.columns([2, 1, 1])
            with c1:
                st.markdown(f"### 🏟️ {res['home_team']} vs {res['away_team']}")
                st.caption(f"📅 台北時間: {res['kickoff_tpe'].strftime('%m-%d %H:%M')}")
                if res['news']:
                    st.caption(f"📰 最新消息: {res['news'][0]['title']}")
            with c2:
                st.metric("Home Win", f"{res['home_prob']:.1%}")
                st.metric("Away Win", f"{res['away_prob']:.1%}")
            with c3:
                st.write("**即時賠率**")
                if res['market_odds']:
                    for o in res['market_odds']['bookmakers'][0]['markets'][0]['outcomes']:
                        st.write(f"{o['name']}: `{o['price']}`")
                else:
                    st.write("未開盤")
            st.divider()
