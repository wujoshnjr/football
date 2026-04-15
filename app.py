import streamlit as st
import pandas as pd
import sqlite3
import numpy as np
from datetime import datetime

# 🔥 引入我們剛做的模組
from football.model import TeamModel, build_matrix
from football.simulation import monte_carlo, calc_probs
from football.betting import edge, kelly

# ==========================================
# ⚙️ 資料庫初始化
# ==========================================
DB_NAME = "zeus_master.db"

def init_db():
    conn = sqlite3.connect(DB_NAME, check_same_thread=False)
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS matches (
            m_id TEXT PRIMARY KEY,
            timestamp DATETIME,
            league TEXT,
            home_team TEXT,
            away_team TEXT,
            home_odds REAL,
            draw_odds REAL,
            away_odds REAL,
            p_home REAL,
            p_draw REAL,
            p_away REAL,
            edge REAL,
            kelly_stake REAL,
            rec_bet TEXT,
            score_matrix TEXT
        )
    ''')
    conn.commit()
    return conn

conn = init_db()

# ==========================================
# 🖥️ UI 主程式
# ==========================================
def main():
    st.set_page_config(layout="wide", page_title="ZEUS QUANT PRO")

    # Sidebar
    with st.sidebar:
        st.header("🔍 系統過濾")
        search_query = st.text_input("搜尋比賽")
        min_edge = st.slider("最低 Edge (%)", 0.0, 10.0, 4.0) / 100

    st.title("⚛️ ZEUS QUANT PRO — AI FOOTBALL ENGINE")

    tab1, tab2 = st.tabs(["🎯 即時分析", "📚 歷史紀錄"])

    # ==========================================
    # 🎯 TAB 1：分析
    # ==========================================
    with tab1:
        col_inp, col_res = st.columns([1, 2])

        with col_inp:
            with st.container(border=True):
                st.subheader("📥 輸入賽事")

                league = st.text_input("聯賽", "英超")

                c1, c2 = st.columns(2)
                h_team = c1.text_input("主隊", "Man City")
                a_team = c2.text_input("客隊", "Arsenal")

                st.divider()

                st.caption("賠率")
                o1, o2, o3 = st.columns(3)
                h_o = o1.number_input("主勝", value=2.1)
                d_o = o2.number_input("和局", value=3.4)
                a_o = o3.number_input("客勝", value=3.6)

                if st.button("🚀 執行 PRO 模型", use_container_width=True):

                    # ===============================
                    # 🧠 模型核心
                    # ===============================
                    model = TeamModel()

                    # ⚠️ 暫時假資料（之後換 API）
                    matches = [
                        {"home": h_team, "away": a_team, "home_goals": 2, "away_goals": 1},
                        {"home": a_team, "away": h_team, "home_goals": 1, "away_goals": 1},
                    ]

                    model.train(matches)

                    # 預測 λ
                    lh, la = model.predict_lambda(h_team, a_team)

                    # Monte Carlo
                    results = monte_carlo(lh, la)
                    ph, pd, pa = calc_probs(results)

                    # Score matrix
                    mat = build_matrix(lh, la)

                    st.session_state['last_calc'] = (
                        ph, pd, pa, mat,
                        h_o, d_o, a_o,
                        h_team, a_team, league
                    )

        # ==========================================
        # 📊 結果顯示
        # ==========================================
        if 'last_calc' in st.session_state:
            ph, pd, pa, mat, ho, do, ao, ht, at, lg = st.session_state['last_calc']

            with col_res:
                m1, m2, m3, m4 = st.columns(4)

                m1.metric("主勝", f"{ph:.2%}")
                m2.metric("和局", f"{pd:.2%}")
                m3.metric("客勝", f"{pa:.2%}")

                probs = [ph, pd, pa]
                odds = [ho, do, ao]

                edges = [edge(p, o) for p, o in zip(probs, odds)]
                best_idx = np.argmax(edges)
                max_edge = edges[best_idx]

                kelly_stake = kelly(probs[best_idx], odds[best_idx])

                m4.metric("最佳 Edge", f"{max_edge:.2%}", delta=f"{kelly_stake:.2%}")

                # ===============================
                # 📊 詳細分析
                # ===============================
                with st.expander("📊 詳細分析", expanded=True):
                    c1, c2 = st.columns([2, 1])

                    with c1:
                        st.caption("Score Matrix")
                        df_mat = pd.DataFrame(
                            mat,
                            columns=[f"A{i}" for i in range(6)],
                            index=[f"H{i}" for i in range(6)]
                        )

                        st.dataframe(
                            df_mat.style.format("{:.2%}").background_gradient(cmap='Greens'),
                            use_container_width=True
                        )

                    with c2:
                        st.caption("衍生玩法")

                        dnb = ph / (ph + pa)
                        over25 = np.sum(mat[2:, :]) + np.sum(mat[:, 2:])

                        st.write(f"DNB 主勝: {dnb:.2%}")
                        st.write(f"Over 2.5: {over25:.2%}")

                        if st.button("💾 儲存"):
                            m_id = f"{ht}_{at}_{datetime.now().strftime('%m%d')}"

                            conn.execute(
                                "REPLACE INTO matches VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                                (
                                    m_id, datetime.now(), lg, ht, at,
                                    ho, do, ao,
                                    ph, pd, pa,
                                    max_edge, kelly_stake,
                                    ["主", "和", "客"][best_idx],
                                    df_mat.to_json()
                                )
                            )
                            conn.commit()
                            st.success("已存入資料庫")

    # ==========================================
    # 📚 TAB 2：歷史
    # ==========================================
    with tab2:
        st.subheader("📋 歷史紀錄")

        try:
            df = pd.read_sql_query("SELECT * FROM matches ORDER BY timestamp DESC", conn)

            if search_query:
                df = df[
                    df['home_team'].str.contains(search_query) |
                    df['away_team'].str.contains(search_query)
                ]

            st.dataframe(
                df[['timestamp','league','home_team','away_team','p_home','p_draw','p_away','edge','rec_bet']],
                use_container_width=True,
                hide_index=True
            )

        except Exception as e:
            st.error(f"讀取錯誤: {e}")


# ==========================================
# 🚀 啟動
# ==========================================
if __name__ == "__main__":
    main()
