import random
import sqlite3
import pandas as pd
from datetime import datetime

class FootballTradingEngine:
    def __init__(self, db_path='football/history.db'):
        self.db_path = db_path
        self._init_db()

    def _init_db(self):
        """初始化資料庫，如果表不存在則建立"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS predictions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT,
                home_team TEXT,
                away_team TEXT,
                home_prob REAL,
                draw_prob REAL,
                away_prob REAL,
                over25 REAL
            )
        ''')
        conn.commit()
        conn.close()

    def predict(self, home, away):
        """模擬預測邏輯 (你可以在此處接入真正的 Elo 或 Poisson 算法)"""
        h_prob = random.uniform(0.2, 0.6)
        a_prob = random.uniform(0.2, 0.4)
        d_prob = 1.0 - h_prob - a_prob
        
        result = {
            "home_team": home,
            "away_team": away,
            "home_prob": h_prob,
            "draw_prob": d_prob,
            "away_prob": a_prob,
            "over25": random.uniform(0.4, 0.8),
            "top_scores": [("1-0", 12), ("2-1", 10), ("1-1", 8)]
        }
        
        # 自動存入數據庫 (持久化)
        self.save_to_history(result)
        return result

    def save_to_history(self, res):
        """將預測結果存入 SQLite"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO predictions (timestamp, home_team, away_team, home_prob, draw_prob, away_prob, over25)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        ''', (datetime.now().isoformat(), res['home_team'], res['away_team'], 
              res['home_prob'], res['draw_prob'], res['away_prob'], res['over25']))
        conn.commit()
        conn.close()

    def get_all_history(self):
        """讀取歷史紀錄"""
        conn = sqlite3.connect(self.db_path)
        df = pd.read_sql_query("SELECT * FROM predictions ORDER BY id DESC", conn)
        conn.close()
        return df
