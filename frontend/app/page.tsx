export const dynamic = 'force-dynamic';
export const revalidate = 0;
export const fetchCache = 'force-no-store';

type TeamSnapshot = { id: string; name: string; country: string; fifa_rank?: number | null; elo_rating: number };
type Fixture = {
  id: string;
  home_team: TeamSnapshot;
  away_team: TeamSnapshot;
  kickoff_time: string;
  venue?: string | null;
  stage: string;
  status: string;
  home_score?: number | null;
  away_score?: number | null;
};
type Forecast = {
  probabilities: { home_win: number; draw: number; away_win: number };
  expected_goals: { home: number; away: number };
  most_likely_scores: Array<{ score: string; probability: number }>;
  confidence: string;
  model_version: string;
  explanation: string[];
};
type SourceContext = {
  sources_used: string[];
  sources_configured: string[];
  sources_missing: string[];
  reliability_score: number;
  fixture_consensus_score: number;
  model_adjustment_note: string;
};
type FetchResult<T> = { data: T; ok: boolean; error?: string };

const API_BASE_URL = process.env.NEXT_PUBLIC_API_BASE_URL || 'http://localhost:8000';
const fixtureSource = 'auto';
const fixtureSourceLabel = 'auto（cache-first）';
const finalStates = ['finished', 'final', 'full_time'];
const requestTimeoutMs = 5500;
const featuredPredictionLimit = 4;

function isFinal(fixture: Fixture) { return finalStates.includes(fixture.status.toLowerCase()); }
function matchStatus(fixture: Fixture) { return isFinal(fixture) ? '已完賽' : '未開賽'; }
function percent(value: number) { return `${Math.round(value * 100)}%`; }
function displayTime(value: string) {
  if (/^\d{4}-\d{2}-\d{2}$/.test(value)) return value.replaceAll('-', '/');
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) return '時間待定';
  return parsed.toLocaleString('zh-TW', { timeZone: 'Asia/Taipei' });
}

async function getJson<T>(path: string, fallback: T, timeoutMs = requestTimeoutMs): Promise<FetchResult<T>> {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), timeoutMs);
  try {
    const response = await fetch(`${API_BASE_URL}${path}`, { cache: 'no-store', signal: controller.signal });
    if (!response.ok) throw new Error(`${response.status} ${response.statusText}`);
    return { data: await response.json(), ok: true };
  } catch (error) {
    const message = error instanceof Error && error.name === 'AbortError'
      ? `timeout after ${timeoutMs}ms`
      : error instanceof Error ? error.message : 'unknown error';
    return { data: fallback, ok: false, error: message };
  } finally {
    clearTimeout(timer);
  }
}

async function getForecast(fixture: Fixture): Promise<Forecast | null> {
  if (isFinal(fixture)) return null;
  const result = await getJson<Forecast | null>(`/predictions/${fixture.id}?source=${fixtureSource}`, null, 4500);
  return result.data;
}

function StatusChip({ ok, label }: { ok: boolean; label: string }) {
  return <span className={ok ? 'chip ok' : 'chip bad'}>{label}</span>;
}

function PercentBar({ label, value }: { label: string; value: number }) {
  return <div className="percentRow"><div className="percentHeader"><span>{label}</span><strong>{percent(value)}</strong></div><div className="track"><div className="bar" style={{ width: percent(value) }} /></div></div>;
}

function MatchCard({ fixture, forecast, showPrediction = false }: { fixture: Fixture; forecast: Forecast | null; showPrediction?: boolean }) {
  const done = isFinal(fixture);
  return (
    <article className="card">
      <div className="cardTop"><span>{fixture.stage}</span><span>{matchStatus(fixture)}</span></div>
      <h2>{fixture.home_team.name} vs {fixture.away_team.name}</h2>
      <p className="time">{displayTime(fixture.kickoff_time)}</p>
      {fixture.venue ? <p className="time">{fixture.venue}</p> : null}
      {done ? <>
        <div className="metrics"><div><span>最終比分</span><strong>{fixture.home_score} : {fixture.away_score}</strong></div><div><span>卡片類型</span><strong>結果</strong></div></div>
        <ul className="reasons"><li>已完賽，只顯示比分，不把賽後資料混入賽前預測。</li></ul>
      </> : forecast ? <>
        <div className="probabilities"><PercentBar label="主勝" value={forecast.probabilities.home_win} /><PercentBar label="和局" value={forecast.probabilities.draw} /><PercentBar label="客勝" value={forecast.probabilities.away_win} /></div>
        <div className="metrics"><div><span>預期進球</span><strong>{forecast.expected_goals.home} : {forecast.expected_goals.away}</strong></div><div><span>信心等級</span><strong>{forecast.confidence}</strong></div></div>
        <div className="scores">{forecast.most_likely_scores.slice(0, 3).map((item) => <span key={item.score}>{item.score} · {percent(item.probability)}</span>)}</div>
        <ul className="reasons">{forecast.explanation.slice(0, 4).map((item) => <li key={item}>{item}</li>)}</ul>
        <p className="version">Model: {forecast.model_version}</p>
      </> : showPrediction ? <p className="warning">預測暫時不可用，頁面已先載入賽程。</p> : <div className="metrics"><div><span>資料狀態</span><strong>賽程已載入</strong></div><div><span>AI 分析</span><strong>熱門區顯示</strong></div></div>}
    </article>
  );
}

export default async function HomePage() {
  const [fixtureResult, sourceResult] = await Promise.all([
    getJson<Fixture[]>(`/fixtures?source=${fixtureSource}`, []),
    getJson<SourceContext | null>('/data-sources/context', null),
  ]);

  const fixtures = fixtureResult.data;
  const sourceContext = sourceResult.data;
  const finalCount = fixtures.filter(isFinal).length;
  const upcoming = fixtures.filter((fixture) => !isFinal(fixture));
  const featured = upcoming.slice(0, featuredPredictionLimit);
  const forecastPairs = await Promise.all(featured.map(async (fixture) => [fixture.id, await getForecast(fixture)] as const));
  const forecastByFixture = new Map(forecastPairs);
  const topTeams = Array.from(new Map(fixtures.flatMap((fixture) => [fixture.home_team, fixture.away_team]).map((team) => [team.id, team])).values()).sort((a, b) => b.elo_rating - a.elo_rating).slice(0, 5);
  const backendHealthy = fixtureResult.ok && sourceResult.ok;
  const fixtureHealthy = fixtureResult.ok && fixtures.length > 0;

  return (
    <main className="page">
      <nav className="topbar"><div className="brand"><span>⚽</span> World Cup IQ</div><div className="navlinks"><a href="#diagnostics">診斷</a><a href="#schedule">賽程</a><a href="#ai">AI預測</a><a href="#sources">資料源</a><a href="#teams">球隊</a></div></nav>
      <section className="hero">
        <p className="eyebrow">World Cup Match Intelligence</p><h1>世界盃足球情報站</h1>
        <p className="subtitle">Vercel 前端連接後端 API，整合世界盃賽程、比分、AI 賽前分析與資料源透明度。首頁使用 cache-first 賽程來源，避免外部資料源拖慢頁面。</p>
        <div className="heroActions"><a href="#diagnostics">先看系統狀態</a><a href="#schedule">查看賽程</a><a href="#ai">AI 預測</a></div>
        <div className="metrics heroMetrics"><div><span>追蹤賽事</span><strong>{fixtures.length}</strong></div><div><span>未開賽</span><strong>{upcoming.length}</strong></div><div><span>已完賽</span><strong>{finalCount}</strong></div></div>
      </section>
      <section className="section" id="diagnostics">
        <div className="sectionHead"><p>Diagnostics</p><h2>系統狀態與問題診斷</h2><span>{fixtureSourceLabel}</span></div>
        <div className="diagnosticGrid">
          <div className="panel"><p className="eyebrow">Frontend</p><h2>Vercel 前端</h2><StatusChip ok={backendHealthy} label={backendHealthy ? '已連線' : '待確認'} /><p className="time">API Base：{API_BASE_URL}</p>{!fixtureResult.ok ? <p className="warning">/fixtures 失敗：{fixtureResult.error}</p> : null}{!sourceResult.ok ? <p className="warning">/data-sources/context 失敗：{sourceResult.error}</p> : null}</div>
          <div className="panel"><p className="eyebrow">Fixture Source</p><h2>賽程資料來源</h2><StatusChip ok={fixtureHealthy} label={fixtureHealthy ? '已載入' : '待確認'} /><p className="time">目前模式：{fixtureSourceLabel}</p><p className="time">首頁不再直接呼叫 /ingestion/fixtures；即時來源請在後端手動檢查。</p></div>
          <div className="panel"><p className="eyebrow">Market Provider</p><h2>市場資料 API</h2><StatusChip ok={Boolean(sourceContext?.sources_configured?.includes('tournamental_odds'))} label={sourceContext?.sources_configured?.includes('tournamental_odds') ? '已設定' : '未設定'} /><p className="time">Tournamental odds 只作市場共識訊號，不作真實下注或 live betting。</p></div>
        </div>
      </section>
      {fixtures.length === 0 ? <section className="emptyState"><h2>目前沒有賽程資料</h2><p>優先檢查 Render 後端是否部署成功、Vercel 的 NEXT_PUBLIC_API_BASE_URL 是否指向後端，以及 /fixtures?source=auto 是否有資料。</p></section> : null}
      <section className="section" id="ai"><div className="sectionHead"><p>AI Prediction</p><h2>熱門 AI 賽前分析</h2><span>顯示前 {featuredPredictionLimit} 場未開賽比賽，符合世界盃單日多場賽程</span></div><div className="spotlight">{featured.map((fixture) => <MatchCard key={fixture.id} fixture={fixture} forecast={forecastByFixture.get(fixture.id) ?? null} showPrediction />)}</div></section>
      <section className="section" id="schedule"><div className="sectionHead"><p>Schedule</p><h2>完整賽程與比分</h2><span>source={fixtureSourceLabel}，所有時間以台灣時間顯示</span></div><section className="grid">{fixtures.map((fixture) => <MatchCard key={fixture.id} fixture={fixture} forecast={forecastByFixture.get(fixture.id) ?? null} />)}</section></section>
      <section className="dashboardRow"><div className="panel" id="sources"><p className="eyebrow">Data Sources</p><h2>資料源狀態</h2><div className="sourceMeter"><strong>{sourceContext ? Math.round(sourceContext.reliability_score * 100) : 0}%</strong><span>source reliability</span></div><p className="time">已啟用：{sourceContext?.sources_configured?.length ?? 0} 個來源</p><p className="time">待補齊：{sourceContext?.sources_missing?.length ?? 0} 個來源</p><p className="warning">{sourceContext?.model_adjustment_note ?? '尚未取得 source context。'}</p></div><div className="panel" id="teams"><p className="eyebrow">Teams</p><h2>球隊戰力焦點</h2><div className="teamList">{topTeams.map((team) => <div key={team.id}><span>{team.name}</span><strong>{Math.round(team.elo_rating)}</strong></div>)}</div></div></section>
      <section className="articleStrip"><article><p>目前狀態</p><h3>Vercel 前端使用 cache-first 後端賽程，降低外部 API timeout 對首頁的影響。</h3></article><article><p>資料策略</p><h3>source=auto 優先讀取本地快取，沒有快取才退回 demo；source=ingestion 保留給後端檢查。</h3></article><article><p>下一步</p><h3>新增可排程的 fixture cache 產生流程，讓前端讀到穩定快照。</h3></article></section>
      <footer className="footer">World Cup IQ — AI predictions are informational analysis only.</footer>
    </main>
  );
}
