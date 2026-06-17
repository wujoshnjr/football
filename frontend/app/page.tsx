type TeamSnapshot = {
  id: string;
  name: string;
  country: string;
  fifa_rank?: number | null;
  elo_rating: number;
};

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

const API_BASE_URL = process.env.NEXT_PUBLIC_API_BASE_URL || 'http://localhost:8000';
const finalStates = ['finished', 'final', 'full_time'];

function isFinal(fixture: Fixture) {
  return finalStates.includes(fixture.status.toLowerCase());
}

function matchStatus(fixture: Fixture) {
  return isFinal(fixture) ? 'Final' : 'Upcoming';
}

function displayTime(value: string) {
  if (/^\d{4}-\d{2}-\d{2}$/.test(value)) return value.replaceAll('-', '/');
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) return 'Time TBD';
  return parsed.toLocaleString('zh-TW', { timeZone: 'Asia/Taipei' });
}

async function getFixtures(): Promise<Fixture[]> {
  try {
    const response = await fetch(`${API_BASE_URL}/fixtures`, { cache: 'no-store' });
    if (!response.ok) throw new Error('Backend unavailable');
    return response.json();
  } catch {
    return [];
  }
}

async function getForecast(fixture: Fixture): Promise<Forecast | null> {
  if (isFinal(fixture)) return null;
  try {
    const response = await fetch(`${API_BASE_URL}/predictions/${fixture.id}`, { cache: 'no-store' });
    if (!response.ok) throw new Error('Forecast unavailable');
    return response.json();
  } catch {
    return null;
  }
}

async function getSourceContext(): Promise<SourceContext | null> {
  try {
    const response = await fetch(`${API_BASE_URL}/data-sources/context`, { cache: 'no-store' });
    if (!response.ok) throw new Error('Source context unavailable');
    return response.json();
  } catch {
    return null;
  }
}

function PercentBar({ label, value }: { label: string; value: number }) {
  return (
    <div className="percentRow">
      <div className="percentHeader">
        <span>{label}</span>
        <strong>{Math.round(value * 100)}%</strong>
      </div>
      <div className="track">
        <div className="bar" style={{ width: `${Math.round(value * 100)}%` }} />
      </div>
    </div>
  );
}

function MatchCard({ fixture, forecast }: { fixture: Fixture; forecast: Forecast | null }) {
  const done = isFinal(fixture);

  return (
    <article className="card">
      <div className="cardTop">
        <span>{fixture.stage}</span>
        <span>{matchStatus(fixture)}</span>
      </div>
      <h2>{fixture.home_team.name} vs {fixture.away_team.name}</h2>
      <p className="time">{displayTime(fixture.kickoff_time)}</p>
      {fixture.venue ? <p className="time">{fixture.venue}</p> : null}

      {done ? (
        <>
          <div className="metrics">
            <div><span>Final Score</span><strong>{fixture.home_score} : {fixture.away_score}</strong></div>
            <div><span>Card Type</span><strong>Result</strong></div>
          </div>
          <ul className="reasons"><li>Completed match. The card displays the verified score instead of a pre-match forecast.</li></ul>
        </>
      ) : forecast ? (
        <>
          <div className="probabilities">
            <PercentBar label="Home" value={forecast.probabilities.home_win} />
            <PercentBar label="Draw" value={forecast.probabilities.draw} />
            <PercentBar label="Away" value={forecast.probabilities.away_win} />
          </div>
          <div className="metrics">
            <div><span>Expected Goals</span><strong>{forecast.expected_goals.home} : {forecast.expected_goals.away}</strong></div>
            <div><span>Confidence</span><strong>{forecast.confidence}</strong></div>
          </div>
          <div className="scores">
            {forecast.most_likely_scores.slice(0, 3).map((item) => <span key={item.score}>{item.score} · {Math.round(item.probability * 100)}%</span>)}
          </div>
          <ul className="reasons">{forecast.explanation.slice(0, 4).map((item) => <li key={item}>{item}</li>)}</ul>
          <p className="version">Model: {forecast.model_version}</p>
        </>
      ) : (
        <p className="warning">Forecast unavailable. Please check backend data status.</p>
      )}
    </article>
  );
}

export default async function HomePage() {
  const fixtures = await getFixtures();
  const sourceContext = await getSourceContext();
  const forecasts = await Promise.all(fixtures.map((fixture) => getForecast(fixture)));
  const finalCount = fixtures.filter(isFinal).length;
  const upcoming = fixtures.filter((fixture) => !isFinal(fixture));
  const featured = upcoming.slice(0, 2);
  const topTeams = Array.from(new Map(fixtures.flatMap((fixture) => [fixture.home_team, fixture.away_team]).map((team) => [team.id, team])).values()).sort((a, b) => b.elo_rating - a.elo_rating).slice(0, 5);

  return (
    <main className="page">
      <nav className="topbar">
        <div className="brand"><span>⚽</span> World Cup IQ</div>
        <div className="navlinks"><a href="#schedule">賽程</a><a href="#ai">AI預測</a><a href="#teams">球隊</a><a href="#sources">資料源</a></div>
      </nav>

      <section className="hero">
        <p className="eyebrow">World Cup Match Intelligence</p>
        <h1>世界盃足球情報站</h1>
        <p className="subtitle">專注賽程、比分、AI 賽前分析與資料源透明度；不加入鑽石或競猜場。</p>
        <div className="heroActions"><a href="#schedule">查看賽程</a><a href="#ai">AI 預測</a><a href="#sources">資料源狀態</a></div>
        <div className="metrics heroMetrics">
          <div><span>Tracked Matches</span><strong>{fixtures.length}</strong></div>
          <div><span>Upcoming</span><strong>{upcoming.length}</strong></div>
          <div><span>Final</span><strong>{finalCount}</strong></div>
        </div>
      </section>

      <section className="section" id="ai">
        <div className="sectionHead"><p>AI Prediction</p><h2>熱門 AI 賽前分析</h2><span>只顯示未開賽賽事</span></div>
        <div className="spotlight">
          {featured.map((fixture) => <MatchCard key={fixture.id} fixture={fixture} forecast={forecasts[fixtures.indexOf(fixture)]} />)}
        </div>
      </section>

      <section className="section" id="schedule">
        <div className="sectionHead"><p>Schedule</p><h2>完整賽程與比分</h2><span>所有時間以台灣時間顯示</span></div>
        <section className="grid">
          {fixtures.map((fixture, index) => <MatchCard key={fixture.id} fixture={fixture} forecast={forecasts[index]} />)}
        </section>
      </section>

      <section className="dashboardRow">
        <div className="panel" id="sources">
          <p className="eyebrow">Data Sources</p>
          <h2>資料源狀態</h2>
          <div className="sourceMeter"><strong>{sourceContext ? Math.round(sourceContext.reliability_score * 100) : 0}%</strong><span>source reliability</span></div>
          <p className="time">已啟用：{sourceContext?.sources_configured?.length ?? 0} 個來源</p>
          <p className="time">待補齊：{sourceContext?.sources_missing?.length ?? 0} 個來源</p>
        </div>

        <div className="panel" id="teams">
          <p className="eyebrow">Teams</p>
          <h2>球隊戰力焦點</h2>
          <div className="teamList">
            {topTeams.map((team) => <div key={team.id}><span>{team.name}</span><strong>{Math.round(team.elo_rating)}</strong></div>)}
          </div>
        </div>
      </section>

      <section className="articleStrip">
        <article><p>賽事解讀</p><h3>已完賽回顧：只顯示比分，不混入賽前預測</h3></article>
        <article><p>模型筆記</p><h3>下一步接入真實 fixture、form、odds、xG 特徵</h3></article>
        <article><p>產品路線</p><h3>先做情報站，再做會員與個人追蹤功能</h3></article>
      </section>

      <footer className="footer">World Cup IQ — AI predictions are informational analysis only.</footer>
    </main>
  );
}
