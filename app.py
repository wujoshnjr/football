import streamlit as st
import pandas as pd
import io
import pytz
import random
from datetime import datetime, timedelta
from football.engine import FootballTradingEngine

# 設定頁面
st.set_page_config(page_title="Football Trading System v5", layout="wide")

# 初始化引擎
engine = FootballTradingEngine()
tz = pytz.timezone("Asia/Taipei")

st.title("⚽ Football Trading System v5 (Hedge Fund)")

# =========================================
# 🚀 全自動化核心：使用 Cache 封裝流程
# =========================================
@st.cache_data(ttl=3600) # 每小時自動重新計算一次，無需手動按鈕
def run_automated_pipeline():
    teams = ["Man City", "Arsenal", "Liverpool", "Real Madrid", "Bayern", "Inter", "PSG"]
    
    # 1. 產生賽程 (模擬或串接 API)
    matches_to_run = []
    for i in range(10):
        h = random.choice(teams)
        a = random.choice([t for t in teams if t != h])
        kickoff = datetime.utcnow() + timedelta(hours=i)
        matches_to_run.append((h, a, kickoff))
        
    # 2. 執行預測並收集數據
    all_results = []
    for h, a, kickoff in matches_to_run:
        res = engine.predict(h, a)
        res['kickoff_tpe'] = kickoff.replace(tzinfo=pytz.utc).astimezone(tz)
        all_results.append(res)
        
    return all_results

# 只要頁面載入，這裡就會自動跑完所有邏輯
data_list = run_automated_pipeline()

# =========================================
# 📊 UI 顯示區域
# =========================================
st.sidebar.header("📊 系統控制台")
st.sidebar.write(f"最後更新 (台北): {datetime.now(tz).strftime('%H:%M:%S')}")

# 動態輸出報表 (Excel)
df_for_excel = pd.DataFrame(data_list)
output = io.BytesIO()
with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
    df_for_excel.to_excel(writer, index=False, sheet_name='Daily_Predictions')
    
st.sidebar.download_button(
    label="📥 下載動態 Excel 報表",
    data=output.getvalue(),
    file_name=f"Trade_Report_{datetime.now(tz).strftime('%Y%m%d')}.xlsx",
    mime="application/vnd.ms-excel"
)

# 顯示歷史紀錄 (持久化驗證)
if st.sidebar.checkbox("查看數據庫歷史紀錄"):
    st.write("### 🗄️ 數據庫持久化紀錄")
    st.dataframe(engine.get_all_history())

# 顯示今日預測面板
for res in data_list:
    with st.container():
        c1, c2, c3 = st.columns([3, 1, 1])
        with c1:
            st.markdown(f"### 🏟️ {res['home_team']} vs {res['away_team']}")
            st.caption(f"⏰ 開賽時間: {res['kickoff_tpe'].strftime('%m-%d %H:%M')}")
        with c2:
            st.metric("Home", f"{res['home_prob']:.1%}")
            st.metric("Away", f"{res['away_prob']:.1%}")
        with c3:
            st.metric("Over 2.5", f"{res['over25']:.1%}")
        
        st.write(f"**Top Scores:** {' | '.join([s for s, c in res['top_scores']])}")
        st.divider()
import streamlit as st
import pandas as pd
import io
import pytz
import random
from datetime import datetime, timedelta
from football.engine import FootballTradingEngine

# 設定頁面
st.set_page_config(page_title="Football Trading System v5", layout="wide")

# 初始化引擎
engine = FootballTradingEngine()
tz = pytz.timezone("Asia/Taipei")

st.title("⚽ Football Trading System v5 (Hedge Fund)")

# =========================================
# 🚀 全自動化核心：使用 Cache 封裝流程
# =========================================
@st.cache_data(ttl=3600) # 每小時自動重新計算一次，無需手動按鈕
def run_automated_pipeline():
    teams = ["Man City", "Arsenal", "Liverpool", "Real Madrid", "Bayern", "Inter", "PSG"]
    
    # 1. 產生賽程 (模擬或串接 API)
    matches_to_run = []
    for i in range(10):
        h = random.choice(teams)
        a = random.choice([t for t in teams if t != h])
        kickoff = datetime.utcnow() + timedelta(hours=i)
        matches_to_run.append((h, a, kickoff))
        
    # 2. 執行預測並收集數據
    all_results = []
    for h, a, kickoff in matches_to_run:
        res = engine.predict(h, a)
        res['kickoff_tpe'] = kickoff.replace(tzinfo=pytz.utc).astimezone(tz)
        all_results.append(res)
        
    return all_results

# 只要頁面載入，這裡就會自動跑完所有邏輯
data_list = run_automated_pipeline()

# =========================================
# 📊 UI 顯示區域
# =========================================
st.sidebar.header("📊 系統控制台")
st.sidebar.write(f"最後更新 (台北): {datetime.now(tz).strftime('%H:%M:%S')}")

# 動態輸出報表 (Excel)
df_for_excel = pd.DataFrame(data_list)
output = io.BytesIO()
with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
    df_for_excel.to_excel(writer, index=False, sheet_name='Daily_Predictions')
    
st.sidebar.download_button(
    label="📥 下載動態 Excel 報表",
    data=output.getvalue(),
    file_name=f"Trade_Report_{datetime.now(tz).strftime('%Y%m%d')}.xlsx",
    mime="application/vnd.ms-excel"
)

# 顯示歷史紀錄 (持久化驗證)
if st.sidebar.checkbox("查看數據庫歷史紀錄"):
    st.write("### 🗄️ 數據庫持久化紀錄")
    st.dataframe(engine.get_all_history())

# 顯示今日預測面板
for res in data_list:
    with st.container():
        c1, c2, c3 = st.columns([3, 1, 1])
        with c1:
            st.markdown(f"### 🏟️ {res['home_team']} vs {res['away_team']}")
            st.caption(f"⏰ 開賽時間: {res['kickoff_tpe'].strftime('%m-%d %H:%M')}")
        with c2:
            st.metric("Home", f"{res['home_prob']:.1%}")
            st.metric("Away", f"{res['away_prob']:.1%}")
        with c3:
            st.metric("Over 2.5", f"{res['over25']:.1%}")
        
        st.write(f"**Top Scores:** {' | '.join([s for s, c in res['top_scores']])}")
        st.divider()
