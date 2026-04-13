import streamlit as st
import pandas as pd
import requests
import pytz
import io
from datetime import datetime, timedelta
from football.engine import FootballTradingEngine

# 1. 基本頁面設定
st.set_page_config(page_title="Football Trading System v5 (Live)", layout="wide")

# 初始化引擎與台北時區
engine = FootballTradingEngine()
tz = pytz.timezone("Asia/Taipei")

st.title("⚽ Football Trading System v5 (Live Data)")

# =========================================
# 🚀 數據整合核心 (API 驅動)
# =========================================
@st.cache_data(ttl=1800) # 每30分鐘自動更新，保證數據真實性
def run_live_pipeline():
    # --- A. 從 Sportmonks 獲取真實賽程 ---
    sm_key = st.secrets["SPORTMONKS_API_KEY"]
    # 獲取今日賽程
    sm_url = f"https://api.sportmonks.com/v3/football/fixtures?api_token={sm_key}&include=participants;league"
    
    try:
        sm_res = requests.get(sm_url).json()
        raw_fixtures = sm_res.get('data', [])
    except Exception as e:
        st.error(f"Sportmonks 連線失敗: {e}")
        raw_fixtures = []

    # --- B. 從 The Odds API 獲取真實賠率 ---
    odds_key = st.secrets["ODDS_API_KEY"]
    # 以英超為例 (soccer_epl)，你可以根據需要修改聯賽代碼
    odds_url = f"https://api.the-odds-api.com/v4/sports/soccer_epl/odds/?apiKey={odds_key}&regions=eu"
    
    try:
        odds_res = requests.get(odds_url).json()
        # 建立快速比對字典 {(主隊, 客隊): 賠率數據}
        odds_lookup = { (m['home_team'], m['away_team']): m for m in odds_res }
    except:
        odds_lookup = {}

    # --- C. 整合與預測 ---
    final_data = []
    
    for f in raw_fixtures:
        # 提取真實隊名與時間
        try:
            home = f['participants'][0]['name']
            away = f['participants'][1]['name']
            start_time_str = f['starting_at'] # YYYY-MM-DD HH:MM:SS
            
            # 呼叫模型運算
            res = engine.predict(home, away)
            
            # 時間轉換 (UTC -> TPE)
            utc_dt = datetime.strptime(start_time_str, '%Y-%m-%d %H:%M:%S')
            res['kickoff_tpe'] = utc_dt.replace(tzinfo=pytz.utc).astimezone(tz)
            
            # 匹配賠率
            res['market_odds'] = odds_lookup.get((home, away), None)
            
            # 抓取新聞 (News API)
            news_key = st.secrets["NEWS_API_KEY"]
            news_url = f"https://newsapi.org/v2/everything?q={home}&apiKey={news_key}&pageSize=1"
            res['news'] = requests.get(news_url).json().get('articles', [])

            final_data.append(res)
        except (KeyError, IndexError):
            continue
            
    return final_data

# 啟動自動化流水線
with st.spinner("正在同步全球即時賽事數據..."):
    live_matches = run_live_pipeline()

# =========================================
# 📊 側邊欄控制與動態 Excel 輸出
# =========================================
st.sidebar.header("📊 系統控制台")
st.sidebar.write(f"最後更新: {datetime.now(tz).strftime('%H:%M:%S')}")

if live_matches:
    # 處理 Excel 匯出 (移除時區以避免 ValueError)
    df_excel = pd.DataFrame(live_matches).copy()
    if 'kickoff_tpe' in df_excel.columns:
        df_excel['kickoff_tpe'] = df_excel['kickoff_tpe'].dt.strftime('%Y-%m-%d %H:%M')
    if 'top_scores' in df_excel.columns:
        df_excel['top_scores'] = df_excel['top_scores'].apply(lambda x: " | ".join([str(i[0]) for i in x]))
    
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
        df_excel.to_excel(writer, index=False, sheet_name='Live_Predictions')
    
    st.sidebar.download_button(
        label="📥 下載今日真實預測報表",
        data=output.getvalue(),
        file_name=f"Real_Time_Report_{datetime.now(tz).strftime('%Y%m%d')}.xlsx",
        mime="application/vnd.ms-excel"
    )

# 歷史持久化顯示
if st.sidebar.checkbox("查看數據庫持久化紀錄"):
    st.dataframe(engine.get_all_history())

# =========================================
# 🏟️ 主介面顯示 (真實比賽)
# =========================================
if not live_matches:
    st.warning("目前時段暫無真實比賽數據，請確認 API Key 或聯賽設定。")
else:
    for res in live_matches:
        with st.container():
            col1, col2, col3 = st.columns([2, 1, 1])
            
            with col1:
                st.markdown(f"### 🏟️ {res['home_team']} vs {res['away_team']}")
                st.caption(f"📅 開賽時間 (台北): {res['kickoff_tpe'].strftime('%m-%d %H:%M')}")
                
                # 顯示新聞
                if res['news']:
                    with st.expander("📰 相關新聞摘要"):
                        st.write(f"**{res['news'][0]['title']}**")
                        st.write(f"[閱讀全文]({res['news'][0]['url']})")

            with col2:
                st.write("**模型預測機率**")
                st.metric("Home Win", f"{res['home_prob']:.1%}")
                st.metric("Away Win", f"{res['away_prob']:.1%}")
                st.metric("Draw", f"{res['draw_prob']:.1%}")

            with col3:
                st.write("**市場即時賠率**")
                if res['market_odds']:
                    for outcome in res['market_odds']['bookmakers'][0]['markets'][0]['outcomes']:
                        st.write(f"{outcome['name']}: `{outcome['price']}`")
                else:
                    st.info("尚未開盤")

            # 顯示預測比分
            scores_str = " | ".join([str(s[0]) for s in res['top_scores']])
            st.write(f"🎯 **精確比分預測:** {scores_str}")
            st.divider()
