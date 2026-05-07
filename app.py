import os
import math
import random
import hashlib
import sqlite3
from datetime import datetime, timedelta

import dash
from dash import dcc, html, Input, Output
from dash.exceptions import PreventUpdate
import dash_bootstrap_components as dbc
import plotly.express as px
import plotly.graph_objects as go
import pandas as pd
import requests

# ---------- 啟動診斷 (僅顯示設定狀態) ----------
print("===== APP STARTUP =====", flush=True)
_keys = [
    "ODDS_API_KEY", "SPORTMONKS_API_KEY", "SPORTS_API_KEY",
    "APIFOOTBALL_API_KEY", "FOOTBALL_DATA_API_KEY",
    "NEWS_API_KEY", "SERPAPI_KEY", "RAPIDAPI_KEY"
]
for k in _keys:
    if os.environ.get(k):
        print(f"✅ {k} 已設定", flush=True)
    else:
        print(f"❌ {k} 未設定", flush=True)
print("------------------------", flush=True)

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

# ---------- 真實強度系統 (基於聯賽排名) ----------
standings_cache = {}

def load_standings():
    global standings_cache
    if standings_cache and standings_cache.get("timestamp") > datetime.now() - timedelta(hours=1):
        return standings_cache
    fd_key = os.environ.get("FOOTBALL_DATA_API_KEY")
    if not fd_key:
        return {}
    headers = {"X-Auth-Token": fd_key}
    standings = {}
    for code in ["PL", "PD", "BL1", "SA", "FL1"]:
        try:
            url = f"https://api.football-data.org/v4/competitions/{code}/standings"
            resp = requests.get(url, headers=headers, timeout=10)
            if resp.status_code == 200:
                data = resp.json().get("standings", [])
                for table in data:
                    if table["type"] == "TOTAL":
                        for row in table["table"]:
                            name = row["team"]["name"]
                            standings[name] = row["position"]
        except Exception:
            pass
    standings["timestamp"] = datetime.now()
    standings_cache = standings
    return standings

def team_strength(name):
    standings = load_standings()
    if name in standings:
        rank = standings[name]
        return 0.7 + (21 - rank) / 20 * 0.6
    return 0.80 + (int(hashlib.md5(name.encode()).hexdigest()[:8], 16) % 46) / 100.0

def compute_lambdas(home, away):
    base = 1.4
    h_str = team_strength(home)
    a_str = team_strength(away)
    return base * h_str * 1.05, base * a_str * 0.95

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

# ---------- API 整合 (各模組皆提供狀態回傳) ----------
def fetch_live_data():
    """回傳 (matches, source_status)"""
    odds_key = os.environ.get("ODDS_API_KEY")
    if odds_key:
        try:
            url = "https://api.the-odds-api.com/v4/sports/soccer/odds/"
            resp = requests.get(url, params={
                "apiKey": odds_key, "regions": "eu", "markets": "h2h", "oddsFormat": "decimal"
            }, timeout=10)
            if resp.status_code == 200:
                data = resp.json()
                matches = []
                for g in data:
                    home = g.get("home_team")
                    away = g.get("away_team")
                    if not home or not away: continue
                    book = g.get("bookmakers", [])
                    if not book: continue
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
                    return matches, f"✅ Odds API - {len(matches)} 場"
                else:
                    return get_demo_matches(), "⚠️ Odds API 無有效賽事，使用演示數據"
            else:
                return get_demo_matches(), f"❌ Odds API 錯誤 ({resp.status_code})，使用演示數據"
        except Exception as e:
            return get_demo_matches(), f"❌ Odds API 異常，使用演示數據"
    # 備援 Football-Data
    football_key = os.environ.get("FOOTBALL_DATA_API_KEY")
    if football_key:
        try:
            today = datetime.now().strftime("%Y-%m-%d")
            url = "https://api.football-data.org/v4/matches"
            headers = {"X-Auth-Token": football_key}
            params = {"dateFrom": today, "dateTo": today, "status": "SCHEDULED"}
            resp = requests.get(url, headers=headers, params=params, timeout=10)
            if resp.status_code == 200:
                matches_data = resp.json().get("matches", [])
                matches = []
                for m in matches_data:
                    matches.append({
                        "league": m["competition"]["name"],
                        "home": m["homeTeam"]["name"],
                        "away": m["awayTeam"]["name"],
                        "odds": [round(random.uniform(1.5, 2.8), 2),
                                 round(random.uniform(3.0, 4.0), 2),
                                 round(random.uniform(2.5, 5.0), 2)]
                    })
                if matches:
                    return matches, f"✅ Football-Data 賽程備援 - {len(matches)} 場 (模擬賠率)"
                else:
                    return get_demo_matches(), "⚠️ Football-Data 無賽程，使用演示數據"
            else:
                return get_demo_matches(), f"❌ Football-Data 錯誤 ({resp.status_code})，使用演示數據"
        except Exception:
            return get_demo_matches(), "❌ Football-Data 異常，使用演示數據"
    return get_demo_matches(), "🔸 無 API 可用，使用演示數據"

def fetch_standings(league_name):
    fd_key = os.environ.get("FOOTBALL_DATA_API_KEY")
    if not fd_key:
        return None, "❌ FOOTBALL_DATA_API_KEY 未設定"
    try:
        league_codes = {"英超": "PL", "西甲": "PD", "德甲": "BL1", "意甲": "SA", "法甲": "FL1"}
        code = league_codes.get(league_name)
        if not code:
            return None, "不支援的聯賽"
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
            return standings[:10], f"✅ Football-Data - {league_name}"
        else:
            return None, f"❌ API 錯誤 ({resp.status_code})"
    except Exception as e:
        return None, f"❌ 請求異常: {str(e)[:50]}"

def fetch_news():
    news_key = os.environ.get("NEWS_API_KEY")
    if not news_key:
        return [], "❌ NEWS_API_KEY 未設定"
    try:
        url = "https://newsapi.org/v2/everything"
        params = {"q": "football OR soccer", "apiKey": news_key, "pageSize": 5, "sortBy": "publishedAt"}
        resp = requests.get(url, params=params, timeout=10)
        if resp.status_code == 200:
            articles = resp.json().get("articles", [])
            return [{"title": a["title"], "source": a["source"]["name"], "url": a["url"], "publishedAt": a["publishedAt"][:10]} for a in articles], "✅ News API"
        else:
            return [], f"❌ News API 錯誤 ({resp.status_code})"
    except Exception as e:
        return [], f"❌ News API 異常"

# ---------- 卡片 UI ----------
def create_match_card(match):
    lambda_h, lambda_a = compute_lambdas(match['home'], match['away'])
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
    html.Div(id="data-source-alert", className="mb-3"),
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
    dcc.Interval(id="live-interval", interval=30 * 60 * 1000),
    html.Footer([
        html.Hr(),
        html.P("⚠️ 本網站僅供數據分析與學術研究，不構成任何投注建議。請遵守當地法律，理性看待預測結果。",
               className="text-muted small")
    ], className="mt-4")
], fluid=True)

# ---------- 回調 ----------
@app.callback(
    Output("data-source-alert", "children"),
    Input("live-interval", "n_intervals")
)
def update_data_alert(n):
    _, status = fetch_live_data()
    if "演示" in status:
        return dbc.Alert(status, color="warning")
    return dbc.Alert(status, color="info")

@app.callback(
    [Output("stat-matches", "children"),
     Output("stat-leagues", "children"),
     Output("stat-advice", "children"),
     Output("stat-news", "children")],
    Input("live-interval", "n_intervals")
)
def update_stats(n):
    matches, _ = fetch_live_data()
    cnt = len(matches)
    leagues = len(set(m["league"] for m in matches))
    if matches:
        m = matches[0]
        lambda_h, lambda_a = compute_lambdas(m['home'], m['away'])
        p_h, p_d, p_a = compute_probs(lambda_h, lambda_a)
        k_h, k_d, k_a = kelly(p_h, m['odds'][0]), kelly(p_d, m['odds'][1]), kelly(p_a, m['odds'][2])
        best = max(k_h, k_d, k_a)
        if best == k_h: adv = f"主勝 {best:.0%}"
        elif best == k_d: adv = f"和局 {best:.0%}"
        else: adv = f"客勝 {best:.0%}"
    else:
        adv = "無"
    news, _ = fetch_news()
    return str(cnt), str(leagues), adv, f"{len(news)} 則"

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
    matches, _ = fetch_live_data()
    cards = [create_match_card(m) for m in matches]
    if matches:
        m = matches[0]
        lambda_h, lambda_a = compute_lambdas(m['home'], m['away'])
        p_h, p_d, p_a = compute_probs(lambda_h, lambda_a)
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

# ---------- 新聞分頁 ----------
@app.callback(
    Output("news-container", "children"),
    Input("main-tabs", "active_tab")
)
def show_news(active):
    if active != "tab-news":
        raise PreventUpdate
    articles, status = fetch_news()
    alert = dbc.Alert(status, color="info" if "❌" not in status else "danger", className="mb-2")
    if not articles:
        return html.Div([alert, html.P("目前沒有新聞。", className="text-muted")])
    return html.Div([alert] + [
        dbc.Card(
            dbc.CardBody([
                html.H5(a["title"], className="text-info"),
                html.P(f"{a['source']} · {a['publishedAt']}", className="text-muted small"),
                html.A("閱讀全文", href=a["url"], target="_blank", className="btn btn-sm btn-outline-info")
            ]),
            className="mb-2 bg-dark"
        ) for a in articles
    ])

# ---------- 圖表下拉 ----------
@app.callback(
    Output("chart-match-select", "options"),
    Input("main-tabs", "active_tab")
)
def fill_dropdown(active):
    if active != "tab-charts":
        raise PreventUpdate
    matches, _ = fetch_live_data()
    return [{"label": f"{m['home']} vs {m['away']} ({m['league']})", "value": i} for i, m in enumerate(matches)]

# ---------- 深度圖表 ----------
@app.callback(
    [Output("prob-bar-chart", "figure"),
     Output("goal-dist-chart", "figure"),
     Output("scoreline-heatmap", "figure")],
    Input("chart-match-select", "value"),
    prevent_initial_call=True
)
def update_charts(idx):
    if idx is None:
        raise PreventUpdate
    matches, _ = fetch_live_data()
    m = matches[idx]
    lambda_h, lambda_a = compute_lambdas(m['home'], m['away'])
    ph, pd_, pa = compute_probs(lambda_h, lambda_a)

    fig1 = px.bar(x=["主勝", "和局", "客勝"], y=[ph, pd_, pa],
                  text=[f"{v:.1%}" for v in [ph, pd_, pa]],
                  color_discrete_sequence=["#0d6efd", "#6c757d", "#dc3545"])
    fig1.update_layout(template="plotly_dark", yaxis_tickformat=".0%")

    goals = list(range(0, 9))
    hd = [poisson_pmf(k, lambda_h) for k in goals]
    ad = [poisson_pmf(k, lambda_a) for k in goals]
    fig2 = go.Figure()
    fig2.add_trace(go.Bar(x=goals, y=hd, name="主隊", marker_color="#0d6efd"))
    fig2.add_trace(go.Bar(x=goals, y=ad, name="客隊", marker_color="#dc3545"))
    fig2.update_layout(barmode="group", template="plotly_dark", yaxis_tickformat=".0%")

    sc = scorelines(lambda_h, lambda_a)
    heat_df = pd.DataFrame(sc, columns=["比分", "概率"])
    heat_df[['主', '客']] = heat_df['比分'].str.split('-', expand=True).astype(int)
    fig3 = px.density_heatmap(heat_df, x="主", y="客", z="概率", color_continuous_scale="blues")
    fig3.update_layout(template="plotly_dark")
    return fig1, fig2, fig3

# ---------- 球隊搜尋 ----------
@app.callback(
    Output("team-search-results", "children"),
    Input("team-search", "value")
)
def search_team(q):
    if not q:
        return html.P("請輸入關鍵詞", className="text-muted")
    # 先嘗試 Sports API
    sports_key = os.environ.get("SPORTS_API_KEY")
    if sports_key:
        try:
            url = "https://api.sportsdata.io/v3/soccer/scores/json/Teams"
            headers = {"Ocp-Apim-Subscription-Key": sports_key}
            resp = requests.get(url, headers=headers, timeout=10)
            if resp.status_code == 200:
                teams = resp.json()
                for team in teams:
                    if q.lower() in team.get("Name", "").lower():
                        return dbc.Row([dbc.Col(dbc.Card(dbc.CardBody([
                            html.H5(team["Name"]),
                            html.P(f"進攻: {team.get('OffensiveRating', '?')} | 防守: {team.get('DefensiveRating', '?')}"),
                        ]), className="mb-2 bg-dark"), width=4)])
        except Exception:
            pass
    # 降級模擬
    mock_db = [
        {"name": "曼城", "attack": 92, "defense": 88},
        {"name": "阿森納", "attack": 85, "defense": 84},
        {"name": "皇馬", "attack": 90, "defense": 86},
        {"name": "巴塞", "attack": 88, "defense": 82},
        {"name": "拜仁", "attack": 93, "defense": 89},
    ]
    results = [t for t in mock_db if q.lower() in t['name'].lower()]
    if not results:
        return html.P("找不到匹配球隊（模擬模式）", className="text-danger")
    return dbc.Row([
        dbc.Col(dbc.Card(dbc.CardBody([
            html.H5(t["name"]),
            html.P(f"進攻: {t['attack']} | 防守: {t['defense']}"),
        ]), className="mb-2 bg-dark"), width=4) for t in results
    ])

# ---------- 聯賽積分榜 ----------
@app.callback(
    Output("standings-table", "children"),
    Input("league-select", "value")
)
def show_standings(league):
    if not league:
        return html.P("請選擇聯賽", className="text-muted")
    data, status = fetch_standings(league)
    alert = dbc.Alert(status, color="info" if "✅" in status else "danger", className="mb-2")
    if data:
        df = pd.DataFrame(data)
        table = dbc.Table.from_dataframe(df, striped=True, bordered=True, hover=True, dark=True)
        return html.Div([alert, table])
    return html.Div([alert, html.P("無法取得積分榜，請稍後再試。")])

# ---------- 歷史歸檔 ----------
@app.callback(
    Output("history-table", "children"),
    Input("main-tabs", "active_tab")
)
def load_history(active):
    if active != "tab-history":
        raise PreventUpdate
    conn = sqlite3.connect('zeus_quant.db')
    df = pd.read_sql_query("SELECT * FROM predictions ORDER BY timestamp DESC LIMIT 50", conn)
    conn.close()
    if df.empty:
        return html.P("暫無歷史記錄", className="text-muted")
    return dbc.Table.from_dataframe(df, striped=True, bordered=True, hover=True, dark=True)

# ---------- 模型調參 ----------
@app.callback(
    Output("model-output", "children"),
    [Input("model-lh", "value"), Input("model-la", "value"), Input("model-mg", "value")]
)
def model_sim(lh, la, mg):
    if None in (lh, la, mg):
        raise PreventUpdate
    ph, pd_, pa = compute_probs(lh, la, mg)
    tops = scorelines(lh, la, mg)[:4]
    return dbc.Card(dbc.CardBody([
        html.H5("模擬結果", className="text-info"),
        dbc.Row([
            dbc.Col(html.H3(f"主勝 {ph:.2%}", className="text-primary")),
            dbc.Col(html.H3(f"和局 {pd_:.2%}", className="text-secondary")),
            dbc.Col(html.H3(f"客勝 {pa:.2%}", className="text-danger")),
        ]),
        html.P("最可能波膽: " + " · ".join([f"{s[0]} ({s[1] * 100:.1f}%)" for s in tops]))
    ]), className="bg-dark")

# ---------- 啟動 ----------
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8050))
    app.run(debug=False, host="0.0.0.0", port=port)
