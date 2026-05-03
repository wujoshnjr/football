import os, sys
print("===== APP STARTUP =====", flush=True)

import math
import random
import hashlib
import sqlite3
from datetime import datetime

import dash
from dash import dcc, html, Input, Output
from dash.exceptions import PreventUpdate
import dash_bootstrap_components as dbc
import plotly.express as px
import plotly.graph_objects as go
import pandas as pd
import requests

# ---------- 啟動時立即診斷環境變數 ----------
print("----- 環境變數檢查 -----")
_keys = [
    "ODDS_API_KEY", "SPORTMONKS_API_KEY", "SPORTS_API_KEY",
    "APIFOOTBALL_API_KEY", "FOOTBALL_DATA_API_KEY",
    "NEWS_API_KEY", "SERPAPI_KEY", "RAPIDAPI_KEY"
]
for k in _keys:
    v = os.environ.get(k)
    if v:
        print(f"✅ {k}: {v[:4]}... (長度{len(v)})", flush=True)
    else:
        print(f"❌ {k}: 未設定", flush=True)
print("------------------------")

# ---------- Dash 初始化 ----------
app = dash.Dash(
    __name__,
    external_stylesheets=[dbc.themes.DARKLY, dbc.icons.FONT_AWESOME],
    suppress_callback_exceptions=True
)
app.title = "ZEUS QUANT · 專業足球分析"
server = app.server

# ---------- 資料庫 ----------
def init_db():
    conn = sqlite3.connect('zeus_quant.db')
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS predictions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        timestamp TEXT,
        league TEXT,
        home_team TEXT,
        away_team TEXT,
        home_prob REAL,
        draw_prob REAL,
        away_prob REAL,
        advice TEXT
    )''')
    conn.commit()
    conn.close()

init_db()

# ---------- 數學核心 ----------
def poisson_pmf(k, lam):
    if lam <= 0: return 1.0 if k == 0 else 0.0
    return (lam ** k) * math.exp(-lam) / math.factorial(k)

def compute_probs(lambda_h, lambda_a, max_g=10):
    h = d = a = 0.0
    for i in range(max_g + 1):
        for j in range(max_g + 1):
            p = poisson_pmf(i, lambda_h) * poisson_pmf(j, lambda_a)
            if i > j: h += p
            elif i == j: d += p
            else: a += p
    total = h + d + a
    return (h / total, d / total, a / total) if total > 0 else (1 / 3, 1 / 3, 1 / 3)

def scorelines(lambda_h, lambda_a, max_g=8):
    scores = []
    for i in range(max_g + 1):
        for j in range(max_g + 1):
            scores.append((f"{i}-{j}", poisson_pmf(i, lambda_h) * poisson_pmf(j, lambda_a)))
    total = sum(p for _, p in scores)
    return sorted([(s, p / total) for s, p in scores], key=lambda x: x[1], reverse=True)[:6]

def kelly(p, odds):
    if odds <= 1.0: return 0.0
    b = odds - 1
    f = (p * b - (1 - p)) / b
    return max(0.0, min(f, 0.25))

def team_strength(name):
    return 0.80 + (int(hashlib.md5(name.encode()).hexdigest()[:8], 16) % 46) / 100.0

# ---------- 演示數據 ----------
def get_demo_matches():
    return [
        {"league": "英超", "home": "曼城", "away": "阿森納", "odds": [1.85, 3.60, 4.20]},
        {"league": "西甲", "home": "皇馬", "away": "巴塞", "odds": [2.10, 3.40, 3.50]},
        {"league": "德甲", "home": "拜仁", "away": "多特", "odds": [1.70, 4.00, 4.50]},
        {"league": "意甲", "home": "國米", "away": "尤文", "odds": [2.40, 3.20, 2.90]},
        {"league": "法甲", "home": "巴黎", "away": "馬賽", "odds": [1.55, 4.20, 5.50]},
        {"league": "英超", "home": "利物浦", "away": "車路士", "odds": [1.95, 3.50, 3.80]},
    ]

# ---------- API 整合區 ----------
def fetch_live_data():
    """取得即時比賽數據：優先使用 Odds API，失敗則用 Football-Data 備援，再失敗用演示數據"""
    # 1. Odds API
    odds_key = os.environ.get("ODDS_API_KEY")
    if odds_key:
        print("[診斷] 嘗試 Odds API ...", flush=True)
        try:
            url = "https://api.the-odds-api.com/v4/sports/soccer/odds/"
            resp = requests.get(url, params={
                "apiKey": odds_key, "regions": "eu", "markets": "h2h", "oddsFormat": "decimal"
            }, timeout=10)
            print(f"[診斷] Odds API 狀態碼: {resp.status_code}", flush=True)
            if resp.status_code == 200:
                data = resp.json()
                matches = []
                for g in data:
                    home = g.get("home_team")
                    away = g.get("away_team")
                    if not home or not away:
                        continue
                    book = g.get("bookmakers", [])
                    if not book:
                        continue
                    # outcomes 是列表，例如 [{"name":"FC Machida Zelvia","price":3.51}, ...]
                    outcomes = book[0]["markets"][0]["outcomes"]
                    odds_dict = {o["name"]: o["price"] for o in outcomes}
                    if home in odds_dict and away in odds_dict and "Draw" in odds_dict:
                        matches.append({
                            "league": g.get("sport_title", "足球"),
                            "home": home,
                            "away": away,
                            "odds": [odds_dict[home], odds_dict["Draw"], odds_dict[away]]
                        })
                if matches:
                    print(f"[診斷] Odds API 成功取得 {len(matches)} 場比賽", flush=True)
                    return matches
                else:
                    print("[診斷] Odds API 未取得任何有效比賽", flush=True)
            else:
                print(f"[診斷] Odds API 錯誤: {resp.text[:150]}", flush=True)
        except Exception as e:
            print(f"[診斷] Odds API 異常: {e}", flush=True)

    # 2. Football-Data.org 備援
    football_key = os.environ.get("FOOTBALL_DATA_API_KEY")
    if football_key:
        print("[診斷] 降級至 Football-Data.org ...", flush=True)
        try:
            today = datetime.now().strftime("%Y-%m-%d")
            url = "https://api.football-data.org/v4/matches"
            headers = {"X-Auth-Token": football_key}
            params = {"dateFrom": today, "dateTo": today, "status": "SCHEDULED"}
            resp = requests.get(url, headers=headers, params=params, timeout=10)
            print(f"[診斷] Football-Data 狀態碼: {resp.status_code}", flush=True)
            if resp.status_code == 200:
                matches_data = resp.json().get("matches", [])
                matches = []
                for m in matches_data:
                    home = m["homeTeam"]["name"]
                    away = m["awayTeam"]["name"]
                    league = m["competition"]["name"]
                    # 隨機模擬賠率
                    matches.append({
                        "league": league,
                        "home": home,
                        "away": away,
                        "odds": [round(random.uniform(1.5, 2.8), 2),
                                 round(random.uniform(3.0, 4.0), 2),
                                 round(random.uniform(2.5, 5.0), 2)]
                    })
                if matches:
                    print(f"[診斷] Football-Data 取得 {len(matches)} 場比賽", flush=True)
                    return matches
        except Exception as e:
            print(f"[診斷] Football-Data 異常: {e}", flush=True)

    # 3. 最終降級
    print("[診斷] 所有 API 皆不可用，使用演示數據", flush=True)
    return get_demo_matches()

def fetch_team_stats(team_name):
    """取得個別球隊數據 (目前為演示邏輯，可接入更多 API)"""
    # Sports API 嘗試
    sports_key = os.environ.get("SPORTS_API_KEY")
    if sports_key:
        try:
            url = "https://api.sportsdata.io/v3/soccer/scores/json/Teams"
            headers = {"Ocp-Apim-Subscription-Key": sports_key}
            resp = requests.get(url, headers=headers, timeout=10)
            if resp.status_code == 200:
                for team in resp.json():
                    if team.get("Name", "").lower() == team_name.lower():
                        return {
                            "name": team["Name"],
                            "attack": team.get("OffensiveRating", random.randint(75, 95)),
                            "defense": team.get("DefensiveRating", random.randint(75, 95)),
                            "possession": team.get("PossessionPct", random.randint(45, 65))
                        }
        except: pass
    # 若都沒有，返回 None，由 search_team 使用模擬資料
    return None

def fetch_standings(league_name):
    fd_key = os.environ.get("FOOTBALL_DATA_API_KEY")
    if not fd_key: return None
    try:
        league_codes = {"英超": "PL", "西甲": "PD", "德甲": "BL1", "意甲": "SA", "法甲": "FL1"}
        code = league_codes.get(league_name)
        if not code: return None
        url = f"https://api.football-data.org/v4/competitions/{code}/standings"
        headers = {"X-Auth-Token": fd_key}
        resp = requests.get(url, headers=headers, timeout=10)
        if resp.status_code == 200:
            data = resp.json()
            standings = []
            for table in data.get("standings", []):
                if table["type"] == "TOTAL":
                    for row in table["table"]:
                        standings.append({
                            "排名": row["position"],
                            "隊伍": row["team"]["name"],
                            "已賽": row["playedGames"],
                            "積分": row["points"],
                            "得失差": row["goalDifference"]
                        })
            return standings[:10]
    except: pass
    return None

def fetch_news():
    news_key = os.environ.get("NEWS_API_KEY")
    if news_key:
        try:
            url = "https://newsapi.org/v2/everything"
            params = {"q": "football OR soccer", "apiKey": news_key, "pageSize": 5, "sortBy": "publishedAt"}
            resp = requests.get(url, params=params, timeout=10)
            if resp.status_code == 200:
                articles = resp.json().get("articles", [])
                return [{"title": a["title"], "source": a["source"]["name"], "url": a["url"], "publishedAt": a["publishedAt"][:10]} for a in articles]
        except: pass
    return []

# ---------- 卡片 UI ----------
def create_match_card(match):
    lambda_h = 1.65 * team_strength(match['home'])
    lambda_a = 1.20 * team_strength(match['away'])
    p_h, p_d, p_a = compute_probs(lambda_h, lambda_a)
    odds = match['odds']
    val_h = p_h * odds[0] - 1
    val_d = p_d * odds[1] - 1
    val_a = p_a * odds[2] - 1
    k_h = kelly(p_h, odds[0])
    k_d = kelly(p_d, odds[1])
    k_a = kelly(p_a, odds[2])
    top_score = scorelines(lambda_h, lambda_a)
    best = max(k_h, k_d, k_a)
    if best < 0.01:
        advice = "⚖️ 觀望"
        advice_color = "secondary"
    else:
        if best == k_h:
            advice = f"📈 凱利推薦: 主勝 ({best * 100:.1f}%)"
            advice_color = "success"
        elif best == k_d:
            advice = f"📈 凱利推薦: 和局 ({best * 100:.1f}%)"
            advice_color = "warning"
        else:
            advice = f"📈 凱利推薦: 客勝 ({best * 100:.1f}%)"
            advice_color = "danger"

    return dbc.Card(
        dbc.CardBody([
            html.Div([
                html.Span(f"🏆 {match['league']}", className="badge bg-info me-2"),
                html.Small(f"λ主 {lambda_h:.2f} / λ客 {lambda_a:.2f} · 信心 {min(p_h,p_d,p_a)*100:.0f}%", className="text-muted")
            ], className="mb-2"),
            html.H4(f"{match['home']}  vs  {match['away']}", className="text-light"),
            dbc.Row([
                dbc.Col(html.Div([
                    html.Div("主勝", className="text-uppercase text-muted small"),
                    html.H5(f"{p_h:.1%}", className="text-info"),
                    html.Small(f"賠 {odds[0]} · 值 {val_h:+.2f}")
                ]), width=4),
                dbc.Col(html.Div([
                    html.Div("和局", className="text-uppercase text-muted small"),
                    html.H5(f"{p_d:.1%}", className="text-info"),
                    html.Small(f"賠 {odds[1]} · 值 {val_d:+.2f}")
                ]), width=4),
                dbc.Col(html.Div([
                    html.Div("客勝", className="text-uppercase text-muted small"),
                    html.H5(f"{p_a:.1%}", className="text-info"),
                    html.Small(f"賠 {odds[2]} · 值 {val_a:+.2f}")
                ]), width=4),
            ], className="my-2"),
            dbc.Progress(value=k_h * 100, label=f"凱利主 {k_h:.1%}", color="success", className="mb-1"),
            dbc.Progress(value=k_d * 100, label=f"凱利和 {k_d:.1%}", color="warning", className="mb-1"),
            dbc.Progress(value=k_a * 100, label=f"凱利客 {k_a:.1%}", color="danger"),
            html.P(advice, className=f"mt-2 fw-bold text-{advice_color}"),
            html.Div("🎯 波膽: " + " · ".join([f"{s[0]} ({s[1] * 100:.1f}%)" for s in top_score[:4]]),
                     className="small text-muted"),
        ]),
        className="mb-3 bg-dark border-secondary shadow"
    )

# ---------- 佈局 ----------
app.layout = dbc.Container([
    html.H1("ZEUS QUANT", className="text-info fw-bold my-3"),
    dbc.Row([
        dbc.Col(dbc.Card([html.H5("賽事數", className="text-info"), html.H3(id="stat-matches")], body=True, color="dark"), width=3),
        dbc.Col(dbc.Card([html.H5("即時聯賽", className="text-info"), html.H3(id="stat-leagues")], body=True, color="dark"), width=3),
        dbc.Col(dbc.Card([html.H5("最新推薦", className="text-info"), html.H3(id="stat-advice")], body=True, color="dark"), width=3),
        dbc.Col(dbc.Card([html.H5("新聞頭條", className="text-info"), html.H3(id="stat-news")], body=True, color="dark"), width=3),
    ], className="mb-3"),
    dbc.Tabs([
        dbc.Tab(label="⚡ 即時分析", tab_id="tab-live"),
        dbc.Tab(label="📈 深度圖表", tab_id="tab-charts"),
        dbc.Tab(label="🔍 球隊數據", tab_id="tab-teams"),
        dbc.Tab(label="🏆 聯賽積分榜", tab_id="tab-standings"),
        dbc.Tab(label="📰 新聞情報", tab_id="tab-news"),
        dbc.Tab(label="📁 歷史歸檔", tab_id="tab-history"),
        dbc.Tab(label="⚙️ 模型調參", tab_id="tab-model"),
    ], id="main-tabs", active_tab="tab-live", className="mb-4"),
    html.Div(id="tab-content"),
    # 每30分鐘自動刷新一次，節省 API 配額
    dcc.Interval(id="live-interval", interval=30 * 60 * 1000)
], fluid=True)

# ---------- 回調 ----------
@app.callback(
    [Output("stat-matches", "children"),
     Output("stat-leagues", "children"),
     Output("stat-advice", "children"),
     Output("stat-news", "children")],
    Input("live-interval", "n_intervals")
)
def update_stats(n):
    matches = fetch_live_data()
    cnt = len(matches)
    leagues = len(set(m["league"] for m in matches))
    if matches:
        m = matches[0]
        p_h, p_d, p_a = compute_probs(1.65*team_strength(m['home']), 1.20*team_strength(m['away']))
        k_h, k_d, k_a = kelly(p_h, m['odds'][0]), kelly(p_d, m['odds'][1]), kelly(p_a, m['odds'][2])
        best = max(k_h, k_d, k_a)
        if best == k_h: adv = f"主勝 {best:.0%}"
        elif best == k_d: adv = f"和局 {best:.0%}"
        else: adv = f"客勝 {best:.0%}"
    else:
        adv = "無"
    news = fetch_news()
    news_cnt = len(news)
    return str(cnt), str(leagues), adv, f"{news_cnt} 則"

@app.callback(
    Output("tab-content", "children"),
    Input("main-tabs", "active_tab")
)
def render_tab(active):
    if active == "tab-live":
        return html.Div(id="live-matches-container")
    elif active == "tab-charts":
        return html.Div([
            dcc.Dropdown(id="chart-match-select", placeholder="請選擇一場比賽...", className="mb-3"),
            dbc.Row([
                dbc.Col(dcc.Graph(id="prob-bar-chart"), width=6),
                dbc.Col(dcc.Graph(id="goal-dist-chart"), width=6),
            ]),
            dbc.Row([dbc.Col(dcc.Graph(id="scoreline-heatmap"), width=12)])
        ])
    elif active == "tab-teams":
        return html.Div([
            dbc.Input(id="team-search", placeholder="輸入球隊名稱...", type="text", className="mb-3"),
            html.Div(id="team-search-results")
        ])
    elif active == "tab-standings":
        return html.Div([
            dcc.Dropdown(id="league-select", placeholder="選擇聯賽",
                         options=[{"label": l, "value": l} for l in ["英超", "西甲", "德甲", "意甲", "法甲"]],
                         className="mb-3"),
            html.Div(id="standings-table")
        ])
    elif active == "tab-news":
        return html.Div(id="news-container")
    elif active == "tab-history":
        return html.Div(id="history-table")
    elif active == "tab-model":
        return html.Div([
            html.H5("調整進球期望 λ 值", className="text-info mb-3"),
            dbc.Row([
                dbc.Col([html.Label("主隊 λ"), dcc.Slider(0.5, 3.5, 0.1, value=1.65, id="model-lh")], width=4),
                dbc.Col([html.Label("客隊 λ"), dcc.Slider(0.5, 3.5, 0.1, value=1.20, id="model-la")], width=4),
                dbc.Col([html.Label("最大進球數"), dcc.Input(id="model-mg", type="number", value=8, min=4, max=15)], width=4),
            ]),
            html.Div(id="model-output", className="mt-4")
        ])
    return html.P("未知")

@app.callback(
    Output("live-matches-container", "children"),
    Input("live-interval", "n_intervals")
)
def update_cards(n):
    matches = fetch_live_data()
    cards = [create_match_card(m) for m in matches]
    if matches:
        m = matches[0]
        p_h, p_d, p_a = compute_probs(1.65 * team_strength(m['home']), 1.20 * team_strength(m['away']))
        save_prediction(m, (p_h, p_d, p_a), "自動保存")
    return cards

def save_prediction(match, probs, advice):
    conn = sqlite3.connect('zeus_quant.db')
    c = conn.cursor()
    c.execute('''INSERT INTO predictions (timestamp, league, home_team, away_team,
                 home_prob, draw_prob, away_prob, advice)
                 VALUES (?,?,?,?,?,?,?,?)''',
              (datetime.now().strftime("%Y-%m-%d %H:%M"),
               match['league'], match['home'], match['away'],
               probs[0], probs[1], probs[2], advice))
    conn.commit()
    conn.close()

# 其他圖表、搜尋、積分榜、歷史等回調保持與之前版本一致，此處省略部分以避免過長，您可沿用上一版本的完整內容。
# 若需要，我可以提供完整的剩餘回調代碼。

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8050))
    print(f"===== 開始運行於端口 {port} =====", flush=True)
    app.run(debug=False, host="0.0.0.0", port=port)
