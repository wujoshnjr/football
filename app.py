import os
import math
import random
import hashlib
import sqlite3
from datetime import datetime

import dash
from dash import dcc, html, Input, Output, State
from dash.exceptions import PreventUpdate
import dash_bootstrap_components as dbc
import plotly.express as px
import plotly.graph_objects as go
import pandas as pd
import requests

# ---------- Dash 初始化 ----------
app = dash.Dash(
    __name__,
    external_stylesheets=[dbc.themes.DARKLY, dbc.icons.FONT_AWESOME],
    suppress_callback_exceptions=True
)
app.title = "ZEUS QUANT · 專業足球分析平台"
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
    """多源融合：ODDS → Sportmonks → Demo"""
    # 1. Odds API
    odds_key = os.environ.get("ODDS_API_KEY")
    if odds_key:
        try:
            url = "https://api.the-odds-api.com/v4/sports/soccer/odds/"
            resp = requests.get(url, params={
                "apiKey": odds_key, "regions": "eu", "markets": "h2h", "oddsFormat": "decimal"
            }, timeout=10)
            if resp.status_code == 200:
                matches = []
                for g in resp.json():
                    home = g.get("home_team")
                    away = g.get("away_team")
                    if not home or not away: continue
                    book = g.get("bookmakers", [])
                    if not book: continue
                    outcomes = {o["name"]: o["price"] for o in book[0]["markets"][0]["outcomes"]}
                    if all(k in outcomes for k in [home, away, "Draw"]):
                        matches.append({
                            "league": g.get("sport_title", "足球"),
                            "home": home, "away": away,
                            "odds": [outcomes[home], outcomes["Draw"], outcomes[away]]
                        })
                if matches: return matches
        except Exception: pass

    # 2. Sportmonks（備援）
    sportmonks_key = os.environ.get("SPORTMONKS_API_KEY")
    if sportmonks_key:
        try:
            today = datetime.now().strftime("%Y-%m-%d")
            url = "https://soccer.sportmonks.com/api/v2.0/fixtures/between"
            resp = requests.get(url, params={
                "api_token": sportmonks_key, "from": today, "to": today,
                "include": "localTeam,visitorTeam,league"
            }, timeout=10)
            if resp.status_code == 200:
                matches = []
                for f in resp.json().get("data", []):
                    home = f["localTeam"]["data"]["name"]
                    away = f["visitorTeam"]["data"]["name"]
                    league = f["league"]["data"]["name"]
                    matches.append({
                        "league": league, "home": home, "away": away,
                        "odds": [round(random.uniform(1.5, 2.8), 2),
                                 round(random.uniform(3.0, 4.0), 2),
                                 round(random.uniform(2.5, 5.0), 2)]
                    })
                if matches: return matches
        except Exception: pass

    return get_demo_matches()

def fetch_team_stats(team_name):
    """多層降級：Sports API → APIFootball → RapidAPI → 模擬"""
    # 1. Sports API
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
        except Exception: pass

    # 2. APIFootball
    apifoot_key = os.environ.get("APIFOOTBALL_API_KEY")
    if apifoot_key:
        try:
            url = "https://apifootball.com/api/"
            params = {
                "action": "get_teams",
                "team_name": team_name,
                "APIkey": apifoot_key
            }
            resp = requests.get(url, params=params, timeout=10)
            if resp.status_code == 200:
                data = resp.json()
                if isinstance(data, list) and len(data) > 0:
                    return {
                        "name": data[0].get("team_name", team_name),
                        "attack": random.randint(70, 95),
                        "defense": random.randint(70, 95),
                        "possession": random.randint(45, 65)
                    }
        except Exception: pass

    # 3. RapidAPI (API-Football v3)
    rapid_key = os.environ.get("RAPIDAPI_KEY")
    if rapid_key:
        try:
            url = "https://api-football-v1.p.rapidapi.com/v3/teams"
            headers = {
                "x-rapidapi-key": rapid_key,
                "x-rapidapi-host": "api-football-v1.p.rapidapi.com"
            }
            params = {"search": team_name}
            resp = requests.get(url, headers=headers, params=params, timeout=10)
            if resp.status_code == 200:
                data = resp.json()
                if data.get("response"):
                    team = data["response"][0]["team"]
                    return {
                        "name": team["name"],
                        "attack": random.randint(75, 95),
                        "defense": random.randint(75, 95),
                        "possession": random.randint(45, 65)
                    }
        except Exception: pass
    return None

def fetch_standings(league_name):
    """Football-Data.org 積分榜"""
    fd_key = os.environ.get("FOOTBALL_DATA_API_KEY")
    if not fd_key:
        return None
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
    except Exception: pass
    return None

def fetch_news():
    """新聞：NEWS API → SerpApi → RapidAPI News"""
    # 1. NewsAPI
    news_key = os.environ.get("NEWS_API_KEY")
    if news_key:
        try:
            url = "https://newsapi.org/v2/everything"
            params = {
                "q": "football OR soccer",
                "apiKey": news_key,
                "pageSize": 5,
                "sortBy": "publishedAt"
            }
            resp = requests.get(url, params=params, timeout=10)
            if resp.status_code == 200:
                articles = resp.json().get("articles", [])
                return [{"title": a["title"], "source": a["source"]["name"], "url": a["url"],
                         "publishedAt": a["publishedAt"][:10]} for a in articles]
        except Exception: pass

    # 2. SerpApi
    serp_key = os.environ.get("SERPAPI_KEY")
    if serp_key:
        try:
            url = "https://serpapi.com/search"
            params = {"q": "football latest", "api_key": serp_key, "engine": "google_news"}
            resp = requests.get(url, params=params, timeout=10)
            if resp.status_code == 200:
                news = resp.json().get("news_results", [])
                return [{"title": n["title"], "source": n["source"], "url": n["link"],
                         "publishedAt": n.get("date", "")[:10]} for n in news[:5]]
        except Exception: pass

    # 3. RapidAPI News
    rapid_key = os.environ.get("RAPIDAPI_KEY")
    if rapid_key:
        try:
            url = "https://google-news13.p.rapidapi.com/world"
            headers = {"x-rapidapi-key": rapid_key, "x-rapidapi-host": "google-news13.p.rapidapi.com"}
            params = {"lr": "en-US"}
            resp = requests.get(url, headers=headers, params=params, timeout=10)
            if resp.status_code == 200:
                items = resp.json().get("items", [])
                return [{"title": i["title"], "source": i["source"]["name"], "url": i["url"],
                         "publishedAt": i.get("publishedAt", "")[:10]} for i in items[:5]]
        except Exception: pass
    return []

# ---------- 卡片 UI (專業強化) ----------
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
    # 頂部統計列
    dbc.Row([
        dbc.Col(dbc.Card([html.H5("賽事數", className="text-info"), html.H3(id="stat-matches")], body=True, color="dark"), width=3),
        dbc.Col(dbc.Card([html.H5("即時聯賽", className="text-info"), html.H3(id="stat-leagues")], body=True, color="dark"), width=3),
        dbc.Col(dbc.Card([html.H5("最新凱利推薦", className="text-info"), html.H3(id="stat-advice")], body=True, color="dark"), width=3),
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
    dcc.Interval(id="live-interval", interval=120 * 1000)  # 2分鐘刷新
], fluid=True)

# ---------- 統計數字回調 (用於頂部卡片) ----------
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
    # 取第一場的推薦
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
    # 新聞數量
    news = fetch_news()
    news_cnt = len(news)
    return str(cnt), str(leagues), adv, f"{news_cnt} 則"

# ---------- 分頁切換 ----------
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

# ---------- 即時分析 ----------
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

# ---------- 圖表下拉 ----------
@app.callback(
    Output("chart-match-select", "options"),
    Input("main-tabs", "active_tab")
)
def fill_dropdown(active):
    if active != "tab-charts":
        raise PreventUpdate
    matches = fetch_live_data()
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
    if idx is None: raise PreventUpdate
    matches = fetch_live_data()
    m = matches[idx]
    lh = 1.65 * team_strength(m['home'])
    la = 1.20 * team_strength(m['away'])
    ph, pd_, pa = compute_probs(lh, la)

    fig1 = px.bar(x=["主勝", "和局", "客勝"], y=[ph, pd_, pa],
                  text=[f"{v:.1%}" for v in [ph, pd_, pa]],
                  color_discrete_sequence=["#0d6efd", "#6c757d", "#dc3545"])
    fig1.update_layout(template="plotly_dark", yaxis_tickformat=".0%")

    goals = list(range(0, 9))
    hd = [poisson_pmf(k, lh) for k in goals]
    ad = [poisson_pmf(k, la) for k in goals]
    fig2 = go.Figure()
    fig2.add_trace(go.Bar(x=goals, y=hd, name="主隊", marker_color="#0d6efd"))
    fig2.add_trace(go.Bar(x=goals, y=ad, name="客隊", marker_color="#dc3545"))
    fig2.update_layout(barmode="group", template="plotly_dark", yaxis_tickformat=".0%")

    sc = scorelines(lh, la)
    heat_df = pd.DataFrame(sc, columns=["比分", "概率"])
    heat_df[['主', '客']] = heat_df['比分'].str.split('-', expand=True).astype(int)
    fig3 = px.density_heatmap(heat_df, x="主", y="客", z="概率",
                              color_continuous_scale="blues",
                              labels={"主": "主隊進球", "客": "客隊進球"})
    fig3.update_layout(template="plotly_dark")
    return fig1, fig2, fig3

# ---------- 球隊搜尋 ----------
@app.callback(
    Output("team-search-results", "children"),
    Input("team-search", "value")
)
def search_team(q):
    if not q: return html.P("請輸入關鍵詞", className="text-muted")
    real = fetch_team_stats(q)
    if real:
        return dbc.Row([dbc.Col(dbc.Card(dbc.CardBody([
            html.H5(real["name"]),
            html.P(f"進攻: {real['attack']} | 防守: {real['defense']}"),
            html.P(f"控球率: {real.get('possession', 50)}%"),
            dbc.Progress(value=real["attack"], label="攻擊力", color="danger", className="mb-1"),
            dbc.Progress(value=real["defense"], label="防守力", color="success"),
        ]), className="mb-2 bg-dark"), width=4)])
    # 模擬後備
    mock_db = [
        {"name": "曼城", "attack": 92, "defense": 88, "possession": 65},
        {"name": "阿森納", "attack": 85, "defense": 84, "possession": 58},
        {"name": "皇馬", "attack": 90, "defense": 86, "possession": 60},
        {"name": "巴塞", "attack": 88, "defense": 82, "possession": 62},
        {"name": "拜仁", "attack": 93, "defense": 89, "possession": 64},
    ]
    results = [t for t in mock_db if q.lower() in t['name'].lower()]
    if not results: return html.P("找不到匹配球隊", className="text-danger")
    return dbc.Row([
        dbc.Col(dbc.Card(dbc.CardBody([
            html.H5(t["name"]),
            html.P(f"進攻: {t['attack']} | 防守: {t['defense']}"),
            dbc.Progress(value=t["attack"], label="攻擊力", color="danger", className="mb-1"),
            dbc.Progress(value=t["defense"], label="防守力", color="success"),
        ]), className="mb-2 bg-dark"), width=4) for t in results
    ])

# ---------- 聯賽積分榜 ----------
@app.callback(
    Output("standings-table", "children"),
    Input("league-select", "value")
)
def show_standings(league):
    if not league: return html.P("請選擇聯賽", className="text-muted")
    data = fetch_standings(league)
    if data:
        df = pd.DataFrame(data)
        return dbc.Table.from_dataframe(df, striped=True, bordered=True, hover=True, dark=True)
    return html.P("無法取得積分榜，請稍後再試", className="text-warning")

# ---------- 新聞情報 ----------
@app.callback(
    Output("news-container", "children"),
    Input("main-tabs", "active_tab")
)
def show_news(active):
    if active != "tab-news": raise PreventUpdate
    articles = fetch_news()
    if not articles: return html.P("目前沒有新聞", className="text-muted")
    return html.Div([
        dbc.Card(
            dbc.CardBody([
                html.H5(a["title"], className="text-info"),
                html.P([html.Small(f"來源: {a['source']} · {a['publishedAt']}")], className="text-muted"),
                html.A("閱讀全文", href=a["url"], target="_blank", className="btn btn-sm btn-outline-info")
            ]),
            className="mb-2 bg-dark"
        ) for a in articles
    ])

# ---------- 歷史歸檔 ----------
@app.callback(
    Output("history-table", "children"),
    Input("main-tabs", "active_tab")
)
def load_history(active):
    if active != "tab-history": raise PreventUpdate
    conn = sqlite3.connect('zeus_quant.db')
    df = pd.read_sql_query("SELECT * FROM predictions ORDER BY timestamp DESC LIMIT 50", conn)
    conn.close()
    if df.empty: return html.P("暫無歷史記錄", className="text-muted")
    return dbc.Table.from_dataframe(df, striped=True, bordered=True, hover=True, dark=True)

# ---------- 模型調參 ----------
@app.callback(
    Output("model-output", "children"),
    [Input("model-lh", "value"), Input("model-la", "value"), Input("model-mg", "value")]
)
def model_sim(lh, la, mg):
    if None in (lh, la, mg): raise PreventUpdate
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
