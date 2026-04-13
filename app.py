import streamlit as st
import pandas as pd
import io
import pytz
import random
from datetime import datetime, timedelta
from football.engine import FootballTradingEngine

# 1. 基礎設定
st.set_page_config(page_title="Football Trading System v5", layout="wide")

# 初始化引擎與時區
engine = FootballTradingEngine()
tz = pytz.timezone("Asia/Taipei")

st.title("⚽ Football Trading System v5 (Hedge Fund)")

# 2. 核心運算邏輯 (全自動化快取)
@st.cache_data(ttl=3600)
def run_automated_pipeline():
    teams = ["Man City", "Arsenal", "Liverpool", "Real Madrid", "Bayern", "Inter", "PSG"]
    matches_to_run = []
    
    # 產生賽程
    for i in range(10):
        h = random.choice(teams)
        a = random.choice([t for t in teams if t != h])
        kickoff = datetime.utcnow() + timedelta(hours=i)
        matches_to_run.append((h, a, kickoff))
        
    # 執行預測
    all_results = []
    for h, a, kickoff in matches_to_run:
        res = engine.predict(h, a)
        # 轉換為台北時間
        res['kickoff_tpe'] = kickoff.replace(tzinfo=pytz.utc).astimezone(tz)
        all_results.append(res)
        
    return all_results

# 執行流水線
data_list = run_automated_pipeline()

# 3. 側邊欄控制與 Excel 處理
st.sidebar.header("📊 系統控制台")
st.sidebar.write(f"最後更新 (台北): {datetime.now(tz).strftime('%H:%M:%S')}")

# --- 處理 Excel 匯出數據 (修復 ValueError) ---
def prepare_excel(data):
    df = pd.DataFrame(data).copy()
    
    # 修正：將帶有時區的 datetime 轉換為字串，避免 Excel 報錯
    if 'kickoff_tpe' in df.columns:
        df['kickoff_tpe'] = df['kickoff_tpe'].dt.strftime('%Y-%m-%d %H:%M')
    
    # 修正：將 top_scores 列表轉為字串，方便在 Excel 閱讀
    if 'top_scores' in df.columns:
        df['top_scores'] = df['top_scores'].apply(lambda x: " | ".join([str(i[0]) for i in x]))
        
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
        df.to_excel(writer, index=False, sheet_name='Daily_Predictions')
    return output.getvalue()

excel_data = prepare_excel(data_list)

st.sidebar.download_button(
    label="📥 下載動態 Excel 報表",
    data=excel_data,
    file_name=f"Trade_Report_{datetime.now(tz).strftime('%Y%m%d')}.xlsx",
    mime="application/vnd.ms-excel"
)

# 查看歷史紀錄
if st.sidebar.checkbox("查看數據庫歷史紀錄"):
    st.write("### 🗄️ 數據庫持久化紀錄")
    st.dataframe(engine.get_all_history())

# 4. 主畫面顯示 (專業 UI)
st.subheader("🔥 今日即時預測面板")
for res in data_list:
    with st.container():
        c1, c2, c3 = st.columns([3, 1, 1])
        with c1:
            st.markdown(f"### 🏟️ {res['home_team']} vs {res['away_team']}")
            st.caption(f"⏰ 開賽時間: {res['kickoff_tpe'].strftime('%m-%d %H:%M')}")
        with c2:
            st.metric("Home Win", f"{res['home_prob']:.1%}")
            st.metric("Away Win", f"{res['away_prob']:.1%}")
        with c3:
            st.metric("Draw", f"{res['draw_prob']:.1%}")
            st.metric("Over 2.5", f"{res['over25']:.1%}")
        
        # 顯示比分預測
        scores = [f"{s}" for s, c in res['top_scores']]
        st.write(f"**Top Score Predictions:** {' | '.join(scores)}")
        st.divider()
