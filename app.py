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

# ---------- 立即诊断环境变量 ----------
print("----- 环境变量检查 -----")
_keys = [
    "ODDS_API_KEY", "SPORTMONKS_API_KEY", "SPORTS_API_KEY",
    "APIFOOTBALL_API_KEY", "FOOTBALL_DATA_API_KEY",
    "NEWS_API_KEY", "SERPAPI_KEY", "RAPIDAPI_KEY"
]
for k in _keys:
    v = os.environ.get(k)
    if v:
        print(f"✅ {k}: {v[:4]}... (长度{len(v)})", flush=True)
    else:
        print(f"❌ {k}: 未设置", flush=True)
print("------------------------")

# ---------- Dash 初始化 ----------
app = dash.Dash(
    __name__,
    external_stylesheets=[dbc.themes.DARKLY, dbc.icons.FONT_AWESOME],
    suppress_callback_exceptions=True
)
app.title = "ZEUS QUANT · 专业足球分析平台"
server = app.server

# ---------- 数据库 ----------
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

# ---------- 数学核心 ----------
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

# ---------- 演示数据 ----------
def get_demo_matches():
    return [
        {"league": "英超", "home": "曼城", "away": "阿森纳", "odds": [1.85, 3.60, 4.20]},
        {"league": "西甲", "home": "皇马", "away": "巴萨", "odds": [2.10, 3.40, 3.50]},
        {"league": "德甲", "home": "拜仁", "away": "多特", "odds": [1.70, 4.00, 4.50]},
        {"league": "意甲", "home": "国米", "away": "尤文", "odds": [2.40, 3.20, 2.90]},
        {"league": "法甲", "home": "巴黎", "away": "马赛", "odds": [1.55, 4.20, 5.50]},
        {"league": "英超", "home": "利物浦", "away": "切尔西", "odds": [1.95, 3.50, 3.80]},
    ]

# ---------- API 整合区（含详细诊断） ----------
def fetch_live_data():
    print("[诊断] fetch_live_data() 被调用", flush=True)

    # Odds API
    odds_key = os.environ.get("ODDS_API_KEY")
    if odds_key:
        print(f"[诊断] 尝试 Odds API，Key 前4位：{odds_key[:4]}", flush=True)
        try:
            url = "https://api.the-odds-api.com/v4/sports/soccer/odds/"
            params = {"apiKey": odds_key, "regions": "eu", "markets": "h2h", "oddsFormat": "decimal"}
            resp = requests.get(url, params=params, timeout=10)
            print(f"[诊断] Odds API 状态码: {resp.status_code}", flush=True)
            if resp.status_code == 200:
                data = resp.json()
                print(f"[诊断] Odds API 返回 {len(data)} 场比赛", flush=True)
                matches = []
                for g in data:
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
                if matches:
                    print(f"[诊断] 成功获取 {len(matches)} 场 Odds 比赛", flush=True)
                    return matches
            else:
                print(f"[诊断] Odds API 失败，响应: {resp.text[:200]}", flush=True)
        except Exception as e:
            print(f"[诊断] Odds API 异常: {e}", flush=True)
    else:
        print("[诊断] ODDS_API_KEY 环境变量不存在", flush=True)

    # Sportmonks 备援
    sportmonks_key = os.environ.get("SPORTMONKS_API_KEY")
    if sportmonks_key:
        print("[诊断] 降级至 Sportmonks", flush=True)
        try:
            today = datetime.now().strftime("%Y-%m-%d")
            url = "https://soccer.sportmonks.com/api/v2.0/fixtures/between"
            params = {
                "api_token": sportmonks_key, "from": today, "to": today,
                "include": "localTeam,visitorTeam,league"
            }
            resp = requests.get(url, params=params, timeout=10)
            print(f"[诊断] Sportmonks 状态码: {resp.status_code}", flush=True)
            if resp.status_code == 200:
                data = resp.json().get("data", [])
                print(f"[诊断] Sportmonks 返回 {len(data)} 场", flush=True)
                matches = []
                for f in data:
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
        except Exception as e:
            print(f"[诊断] Sportmonks 异常: {e}", flush=True)

    print("[诊断] 所有 API 不可用，返回演示数据", flush=True)
    return get_demo_matches()

def fetch_team_stats(team_name):
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
                            "队伍": row["team"]["name"],
                            "已赛": row["playedGames"],
                            "积分": row["points"],
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
        advice = "⚖️ 观望"
        advice_color = "secondary"
    else:
        if best == k_h:
            advice = f"📈 凯利推荐: 主胜 ({best * 100:.1f}%)"
            advice_color = "success"
        elif best == k_d:
            advice = f"📈 凯利推荐: 和局 ({best * 100:.1f}%)"
            advice_color = "warning"
        else:
            advice = f"📈 凯利推荐: 客胜 ({best * 100:.1f}%)"
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
                    html.Div("主胜", className="text-uppercase text-muted small"),
                    html.H5(f"{p_h:.1%}", className="text-info"),
                    html.Small(f"赔 {odds[0]} · 值 {val_h:+.2f}")
                ]), width=4),
                dbc.Col(html.Div([
                    html.Div("和局", className="text-uppercase text-muted small"),
                    html.H5(f"{p_d:.1%}", className="text-info"),
                    html.Small(f"赔 {odds[1]} · 值 {val_d:+.2f}")
                ]), width=4),
                dbc.Col(html.Div([
                    html.Div("客胜", className="text-uppercase text-muted small"),
                    html.H5(f"{p_a:.1%}", className="text-info"),
                    html.Small(f"赔 {odds[2]} · 值 {val_a:+.2f}")
                ]), width=4),
            ], className="my-2"),
            dbc.Progress(value=k_h * 100, label=f"凯利主 {k_h:.1%}", color="success", className="mb-1"),
            dbc.Progress(value=k_d * 100, label=f"凯利和 {k_d:.1%}", color="warning", className="mb-1"),
            dbc.Progress(value=k_a * 100, label=f"凯利客 {k_a:.1%}", color="danger"),
            html.P(advice, className=f"mt-2 fw-bold text-{advice_color}"),
            html.Div("🎯 波胆: " + " · ".join([f"{s[0]} ({s[1] * 100:.1f}%)" for s in top_score[:4]]),
                     className="small text-muted"),
        ]),
        className="mb-3 bg-dark border-secondary shadow"
    )

# ---------- 布局 ----------
app.layout = dbc.Container([
    html.H1("ZEUS QUANT", className="text-info fw-bold my-3"),
    dbc.Row([
        dbc.Col(dbc.Card([html.H5("赛事数", className="text-info"), html.H3(id="stat-matches")], body=True, color="dark"), width=3),
        dbc.Col(dbc.Card([html.H5("即时联赛", className="text-info"), html.H3(id="stat-leagues")], body=True, color="dark"), width=3),
        dbc.Col(dbc.Card([html.H5("最新推荐", className="text-info"), html.H3(id="stat-advice")], body=True, color="dark"), width=3),
        dbc.Col(dbc.Card([html.H5("新闻头条", className="text-info"), html.H3(id="stat-news")], body=True, color="dark"), width=3),
    ], className="mb-3"),
    dbc.Tabs([
        dbc.Tab(label="⚡ 即时分析", tab_id="tab-live"),
        dbc.Tab(label="📈 深度图表", tab_id="tab-charts"),
        dbc.Tab(label="🔍 球队数据", tab_id="tab-teams"),
        dbc.Tab(label="🏆 联赛积分榜", tab_id="tab-standings"),
        dbc.Tab(label="📰 新闻情报", tab_id="tab-news"),
        dbc.Tab(label="📁 历史归档", tab_id="tab-history"),
        dbc.Tab(label="⚙️ 模型调参", tab_id="tab-model"),
    ], id="main-tabs", active_tab="tab-live", className="mb-4"),
    html.Div(id="tab-content"),
    dcc.Interval(id="live-interval", interval=120 * 1000)
], fluid=True)

# ---------- 统计数字回调 ----------
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
        if best == k_h: adv = f"主胜 {best:.0%}"
        elif best == k_d: adv = f"和局 {best:.0%}"
        else: adv = f"客胜 {best:.0%}"
    else:
        adv = "无"
    news = fetch_news()
    news_cnt = len(news)
    return str(cnt), str(leagues), adv, f"{news_cnt} 则"

# ---------- 分页切换 ----------
@app.callback(
    Output("tab-content", "children"),
    Input("main-tabs", "active_tab")
)
def render_tab(active):
    if active == "tab-live":
        return html.Div(id="live-matches-container")
    elif active == "tab-charts":
        return html.Div([
            dcc.Dropdown(id="chart-match-select", placeholder="请选择一场比赛...", className="mb-3"),
            dbc.Row([
                dbc.Col(dcc.Graph(id="prob-bar-chart"), width=6),
                dbc.Col(dcc.Graph(id="goal-dist-chart"), width=6),
            ]),
            dbc.Row([dbc.Col(dcc.Graph(id="scoreline-heatmap"), width=12)])
        ])
    elif active == "tab-teams":
        return html.Div([
            dbc.Input(id="team-search", placeholder="输入球队名称...", type="text", className="mb-3"),
            html.Div(id="team-search-results")
        ])
    elif active == "tab-standings":
        return html.Div([
            dcc.Dropdown(id="league-select", placeholder="选择联赛",
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
            html.H5("调整进球期望 λ 值", className="text-info mb-3"),
            dbc.Row([
                dbc.Col([html.Label("主队 λ"), dcc.Slider(0.5, 3.5, 0.1, value=1.65, id="model-lh")], width=4),
                dbc.Col([html.Label("客队 λ"), dcc.Slider(0.5, 3.5, 0.1, value=1.20, id="model-la")], width=4),
                dbc.Col([html.Label("最大进球数"), dcc.Input(id="model-mg", type="number", value=8, min=4, max=15)], width=4),
            ]),
            html.Div(id="model-output", className="mt-4")
        ])
    return html.P("未知")

# ---------- 即时分析 ----------
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
        save_prediction(m, (p_h, p_d, p_a), "自动保存")
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

# ---------- 其他回调（保留必要功能）----------
@app.callback(
    Output("chart-match-select", "options"),
    Input("main-tabs", "active_tab")
)
def fill_dropdown(active):
    if active != "tab-charts": raise PreventUpdate
    matches = fetch_live_data()
    return [{"label": f"{m['home']} vs {m['away']} ({m['league']})", "value": i} for i, m in enumerate(matches)]

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
    fig1 = px.bar(x=["主胜", "和局", "客胜"], y=[ph, pd_, pa],
                  text=[f"{v:.1%}" for v in [ph, pd_, pa]],
                  color_discrete_sequence=["#0d6efd", "#6c757d", "#dc3545"])
    fig1.update_layout(template="plotly_dark", yaxis_tickformat=".0%")
    goals = list(range(0, 9))
    hd = [poisson_pmf(k, lh) for k in goals]
    ad = [poisson_pmf(k, la) for k in goals]
    fig2 = go.Figure()
    fig2.add_trace(go.Bar(x=goals, y=hd, name="主队", marker_color="#0d6efd"))
    fig2.add_trace(go.Bar(x=goals, y=ad, name="客队", marker_color="#dc3545"))
    fig2.update_layout(barmode="group", template="plotly_dark", yaxis_tickformat=".0%")
    sc = scorelines(lh, la)
    heat_df = pd.DataFrame(sc, columns=["比分", "概率"])
    heat_df[['主', '客']] = heat_df['比分'].str.split('-', expand=True).astype(int)
    fig3 = px.density_heatmap(heat_df, x="主", y="客", z="概率",
                              color_continuous_scale="blues",
                              labels={"主": "主队进球", "客": "客队进球"})
    fig3.update_layout(template="plotly_dark")
    return fig1, fig2, fig3

@app.callback(
    Output("team-search-results", "children"),
    Input("team-search", "value")
)
def search_team(q):
    if not q: return html.P("请输入关键词", className="text-muted")
    real = fetch_team_stats(q)
    if real:
        return dbc.Row([dbc.Col(dbc.Card(dbc.CardBody([
            html.H5(real["name"]),
            html.P(f"进攻: {real['attack']} | 防守: {real['defense']}"),
            html.P(f"控球率: {real.get('possession', 50)}%"),
            dbc.Progress(value=real["attack"], label="攻击力", color="danger", className="mb-1"),
            dbc.Progress(value=real["defense"], label="防守力", color="success"),
        ]), className="mb-2 bg-dark"), width=4)])
    mock_db = [
        {"name": "曼城", "attack": 92, "defense": 88, "possession": 65},
        {"name": "阿森纳", "attack": 85, "defense": 84, "possession": 58},
        {"name": "皇马", "attack": 90, "defense": 86, "possession": 60},
        {"name": "巴萨", "attack": 88, "defense": 82, "possession": 62},
        {"name": "拜仁", "attack": 93, "defense": 89, "possession": 64},
    ]
    results = [t for t in mock_db if q.lower() in t['name'].lower()]
    if not results: return html.P("找不到匹配球队", className="text-danger")
    return dbc.Row([
        dbc.Col(dbc.Card(dbc.CardBody([
            html.H5(t["name"]),
            html.P(f"进攻: {t['attack']} | 防守: {t['defense']}"),
            dbc.Progress(value=t["attack"], label="攻击力", color="danger", className="mb-1"),
            dbc.Progress(value=t["defense"], label="防守力", color="success"),
        ]), className="mb-2 bg-dark"), width=4) for t in results
    ])

@app.callback(
    Output("standings-table", "children"),
    Input("league-select", "value")
)
def show_standings(league):
    if not league: return html.P("请选择联赛", className="text-muted")
    data = fetch_standings(league)
    if data:
        df = pd.DataFrame(data)
        return dbc.Table.from_dataframe(df, striped=True, bordered=True, hover=True, dark=True)
    return html.P("无法取得积分榜，请稍后再试", className="text-warning")

@app.callback(
    Output("news-container", "children"),
    Input("main-tabs", "active_tab")
)
def show_news(active):
    if active != "tab-news": raise PreventUpdate
    articles = fetch_news()
    if not articles: return html.P("目前没有新闻", className="text-muted")
    return html.Div([
        dbc.Card(
            dbc.CardBody([
                html.H5(a["title"], className="text-info"),
                html.P([html.Small(f"来源: {a['source']} · {a['publishedAt']}")], className="text-muted"),
                html.A("阅读全文", href=a["url"], target="_blank", className="btn btn-sm btn-outline-info")
            ]),
            className="mb-2 bg-dark"
        ) for a in articles
    ])

@app.callback(
    Output("history-table", "children"),
    Input("main-tabs", "active_tab")
)
def load_history(active):
    if active != "tab-history": raise PreventUpdate
    conn = sqlite3.connect('zeus_quant.db')
    df = pd.read_sql_query("SELECT * FROM predictions ORDER BY timestamp DESC LIMIT 50", conn)
    conn.close()
    if df.empty: return html.P("暂无历史记录", className="text-muted")
    return dbc.Table.from_dataframe(df, striped=True, bordered=True, hover=True, dark=True)

@app.callback(
    Output("model-output", "children"),
    [Input("model-lh", "value"), Input("model-la", "value"), Input("model-mg", "value")]
)
def model_sim(lh, la, mg):
    if None in (lh, la, mg): raise PreventUpdate
    ph, pd_, pa = compute_probs(lh, la, mg)
    tops = scorelines(lh, la, mg)[:4]
    return dbc.Card(dbc.CardBody([
        html.H5("模拟结果", className="text-info"),
        dbc.Row([
            dbc.Col(html.H3(f"主胜 {ph:.2%}", className="text-primary")),
            dbc.Col(html.H3(f"和局 {pd_:.2%}", className="text-secondary")),
            dbc.Col(html.H3(f"客胜 {pa:.2%}", className="text-danger")),
        ]),
        html.P("最可能波胆: " + " · ".join([f"{s[0]} ({s[1] * 100:.1f}%)" for s in tops]))
    ]), className="bg-dark")

# ---------- 启动 ----------
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8050))
    print(f"===== 开始运行于端口 {port} =====", flush=True)
    app.run(debug=False, host="0.0.0.0", port=port)
