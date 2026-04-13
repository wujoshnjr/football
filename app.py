import streamlit as st
import pandas as pd
import requests
import pytz
import io
from datetime import datetime, timedelta
from football.engine import FootballTradingEngine

# 1. 頁面基礎配置
st.set_page_config(page_title="Hedge Fund V5 Pro", layout="wide", initial_sidebar_state="expanded")
engine = FootballTradingEngine()
tz = pytz.timezone("Asia/Taipei")

st.title("⚽ Football Trading System v5 (Live Data)")

# =========================================
# 🛠️ 檢查 Secrets 狀態
# =========================================
SM_KEY = st.secrets.get("SPORTMONKS_API_KEY")
ODDS_KEY = st.secrets.get("ODDS_API_KEY")

if not SM_KEY:
    st.error("❌ 找不到 SPORTMONKS_API_KEY。請至 Streamlit Cloud Settings 填寫。")
    st.stop()

# =========================================
# 🚀 數據整合流水線 (擴大範圍版)
# =========================================
@st.cache_data(ttl=1800)
def run_live_pipeline():
    # --- A. 抓取未來 3 天的賽程，避免當天沒比賽導致空白 ---
    start_date = datetime.now().strftime('%Y-%m-%d')
    end_date = (datetime.now() + timedelta(days=3)).strftime('%Y-%m-%d')
    
    # 修改 URL：加入日期篩選，增加抓到比賽的機率
    sm_url = f"https://api.sportmonks.com/v3/football/fixtures/between/{start_date}/{end_date}?api_token={SM_KEY}&include=participants;league"
    
    final_data = []
    try:
        response = requests.get(sm_url, timeout=15)
        sm_res = response.json()
        
        # 如果有錯誤訊息 (例如權限不足)，直接印在畫面上診斷
        if "error" in sm_res or "message" in sm_res and "subscription" in str(sm_res):
            st.sidebar.warning(f"Sportmonks 提示: {sm_res.get('message', '權限限制')}")

        raw_fixtures = sm_res.get('data', [])
        
        # --- B. 抓取賠率 (The Odds API) ---
        odds_lookup = {}
        if ODDS_KEY:
            # 抓取熱門聯賽賠率
            odds_url = f"https://api.the-odds-api.com/v4/sports/soccer/odds/?apiKey={ODDS_KEY}&regions=eu&markets=h2h"
            try:
                o_res = requests.get(odds_url, timeout=10).json()
                if isinstance(o_res, list):
                    odds_lookup = { (m['home_team'], m['away_team']): m for m in o_res }
            except:
                pass

        # --- C. 整合預測邏輯 ---
        for f in raw_fixtures[:20]: # 最多顯示 20 場
            try:
                home = f['participants'][0]['name']
                away = f['participants'][1]['name']
                league_name = f.get('league', {}).get('name', 'Unknown League')
                
                # 執行模型計算
                res = engine.predict(home, away)
                
                # 時間格式轉化
                utc_dt = datetime.strptime(f['starting_at'], '%Y-%m-%d %H:%M:%S')
                res['kickoff_tpe'] = utc_dt.replace(tzinfo=pytz.utc).astimezone(tz)
                res['league'] = league_name
                
                # 匹配賠率
                res['market_odds'] = odds_lookup.get((home, away), None)
                final_data.append(res)
            except:
                continue
    except Exception as e:
        st.error(f"連線異常: {e}")
        
    return final_data

# 啟動抓取
with st.spinner("🔍 正在掃描全球未來 72 小時賽事數據..."):
    live_matches = run_live_pipeline()

# =========================================
# 📊 側邊欄控制
# =========================================
st.sidebar.header("📊 系統控制台")
st.sidebar.write(f"最後更新 (TPE): {datetime.now(tz).strftime('%H:%M:%S')}")

if live_matches:
    # 下載 Excel
    df_excel = pd.DataFrame(live_matches).copy()
    if 'kickoff_tpe' in df_excel.columns:
        df_excel['kickoff_tpe'] = df_excel['kickoff_tpe'].dt.strftime('%Y-%m-%d %H:%M')
    
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
        df_excel.to_excel(writer, index=False)
    
    st.sidebar.download_button("📥 匯出完整預測報表", output.getvalue(), "Report.xlsx")

# =========================================
# 🏟️ 顯示面板
# =========================================
if not live_matches:
    st.info("💡 目前資料庫為空。這通常代表您的 Sportmonks 方案不支援當前聯賽，或是這幾天沒有比賽。")
    st.image("https://via.placeholder.com/800x200.png?text=Waiting+for+Live+Data+from+API", use_column_width=True)
else:
    for res in live_matches:
        with st.expander(f"⚽ {res['league']}: {res['home_team']} vs {res['away_team']}", expanded=True):
            c1, c2, c3 = st.columns([2, 1, 1])
            with c1:
                st.write(f"⏰ **開賽時間:** {res['kickoff_tpe'].strftime('%m/%d %H:%M')}")
                st.write(f"🏆 **聯賽:** {res['league']}")
            with c2:
                st.metric("模型勝率 (Home)", f"{res['home_prob']:.1%}")
                st.metric("模型勝率 (Away)", f"{res['away_prob']:.1%}")
            with c3:
                st.write("**市場即時賠率**")
                if res['market_odds']:
                    for o in res['market_odds']['bookmakers'][0]['markets'][0]['outcomes']:
                        st.write(f"{o['name']}: `{o['price']}`")
                else:
                    st.caption("市場暫未開盤")
