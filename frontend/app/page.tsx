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

export default async function HomePage() {
  const fixtures = await getFixtures();
  const forecasts = await Promise.all(fixtures.map((fixture) => getForecast(fixture)));
  const finalCount = fixtures.filter(isFinal).length;
  const upcomingCount = fixtures.length - finalCount;

  return (
    <main className="page">
      <section className="hero">
        <p className="eyebrow">World Cup Match Intelligence</p>
        <h1>世界盃足球情報站</h1>
        <p className="subtitle">專注賽程、比分、AI 賽前分析與資料源透明度；不加入鑽石或競猜玩法。</p>
        <div className="metrics">
          <div><span>Tracked Matches</span><strong>{fixtures.length}</strong></div>
          <div><span>Upcoming</span><strong>{upcomingCount}</strong></div>
          <div><span>Final</span><strong>{finalCount}</strong></div>
        </div>
      </section>

      <section className="grid">
        {fixtures.map((fixture, index) => {
          const forecast = forecasts[index];
          const done = isFinal(fixture);
          return (
            <article className="card" key={fixture.id}>
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
        })}
      </section>
    </main>
  );
}
