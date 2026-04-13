import streamlit as st
from football.engine import FootballTradingEngine
from datetime import datetime, timedelta
import pytz
import random
import pandas as pd
import io

st.set_page_config(layout="wide")
st.title("⚽ Football Trading System v5 (Hedge Fund)")

engine = FootballTradingEngine()
tz = pytz.timezone("Asia/Taipei")

# 🔥 1. 全自動化核心：使用 Cache 封裝
# ttl=3600 代表這段運算每小時只會跑一次。不管你重新整理幾次網頁，它都會直接秒速讀取快取。
@st.cache_data(ttl=3600)
def run_automated_pipeline():
    teams = [
        "Man City", "Arsenal", "Liverpool", "Chelsea", "Barcelona", 
        "Real Madrid", "Atletico Madrid", "Bayern", "Dortmund", "Leipzig",
        "PSG", "Marseille", "Lyon", "Inter", "Juventus", "Milan", "Napoli", "Roma", "Lazio"
    ]
    
    matches = []
    # 產生賽事
    for i in range(20):
        home = random.choice(teams)
        away = random.choice([t for t in teams if t != home])
        kickoff = datetime.utcnow() + timedelta(hours=i)
        matches.append((home, away, kickoff))

    # 計算預測並收集數據，為了後續輸出 Excel 報表做準備
    report_data = []
    for home, away, kickoff in matches:
        result = engine.predict(home, away)
        kickoff_tpe = kickoff.replace(tzinfo=pytz.utc).astimezone(tz)
        
        # 將時間存入 result，方便後續統一處理
        result['kickoff_tpe'] = kickoff_tpe
        report_data.append(result)
        
    return report_data

# 🚀 網頁一打開，這裡就會自動執行流水線，完全不需按鈕
predicted_matches = run_automated_pipeline()

# =========================================
# 顯示比賽（專業版 UI）
# =========================================
for result in predicted_matches:
    with st.container():
        col1, col2, col3 = st.columns([3,1,1])

        with col1:
            st.markdown(f"### 🏟️ {result['home_team']} vs {result['away_team']}")
            st.markdown(f"⏰ 開賽時間（台北）: {result['kickoff_tpe'].strftime('%m-%d %H:%M')}")

        with col2:
            st.metric("Home", f"{result['home_prob']:.1%}")
            st.metric("Draw", f"{result['draw_prob']:.1%}")
            st.metric("Away", f"{result['away_prob']:.1%}")

        with col3:
            st.metric("Over 2.5", f"{result['over25']:.1%}")

        st.markdown("**Top Score Predictions**")
        
        # 假設你的 result["top_scores"] 是一個 list of tuples，例如 [("2-1", 15), ("1-1", 12)]
        scores_str = " | ".join([f"{score}" for score, count in result["top_scores"]])
        st.write(scores_str) # 這裡稍微改寫，用單行顯示比分會讓畫面更緊湊專業

        st.markdown("---")

# =========================================
# 🔥 2. 動態報表輸出 (Excel 自動化)
# =========================================
# 將整理好的預測結果轉成 DataFrame
df_report = pd.DataFrame(predicted_matches)

# 將 DataFrame 寫入記憶體中的 Excel 檔案
buffer = io.BytesIO()
with pd.ExcelWriter(buffer, engine='xlsxwriter') as writer:
    # 你可以在這裡過濾或重新命名欄位，讓匯出的 Excel 更乾淨
    df_report.to_excel(writer, sheet_name='Trading Predictions', index=False)

# 在側邊欄放置下載按鈕
st.sidebar.markdown("### 📊 報表系統")
st.sidebar.download_button(
    label="📥 匯出今日預測報表 (Excel)",
    data=buffer,
    file_name=f"HedgeFund_Report_{datetime.now(tz).strftime('%Y%m%d')}.xlsx",
    mime="application/vnd.ms-excel"
)
