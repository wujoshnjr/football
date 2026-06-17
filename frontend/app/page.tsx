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
  stage: string;
  status: string;
};

type Prediction = {
  fixture_id: string;
  match: string;
  probabilities: {
    home_win: number;
    draw: number;
    away_win: number;
  };
  expected_goals: {
    home: number;
    away: number;
  };
  most_likely_scores: Array<{ score: string; probability: number }>;
  confidence: string;
  model_version: string;
  explanation: string[];
};

const API_BASE_URL = process.env.NEXT_PUBLIC_API_BASE_URL || 'http://localhost:8000';

async function getFixtures(): Promise<Fixture[]> {
  try {
    const response = await fetch(`${API_BASE_URL}/fixtures`, { cache: 'no-store' });
    if (!response.ok) throw new Error('Backend unavailable');
    return response.json();
  } catch {
    return [
      {
        id: 'demo-arg-alg-2026',
        home_team: { id: 'arg', name: 'Argentina', country: 'Argentina', fifa_rank: 1, elo_rating: 2140 },
        away_team: { id: 'alg', name: 'Algeria', country: 'Algeria', fifa_rank: 37, elo_rating: 1760 },
        kickoff_time: '2026-06-17T01:00:00Z',
        stage: 'Group Stage',
        status: 'scheduled'
      }
    ];
  }
}

async function getPrediction(fixtureId: string): Promise<Prediction | null> {
  try {
    const response = await fetch(`${API_BASE_URL}/predictions/${fixtureId}`, { cache: 'no-store' });
    if (!response.ok) throw new Error('Prediction unavailable');
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
  const predictions = await Promise.all(fixtures.map((fixture) => getPrediction(fixture.id)));

  return (
    <main className="page">
      <section className="hero">
        <p className="eyebrow">World Cup AI Prediction MVP</p>
        <h1>世界盃足球預測平台</h1>
        <p className="subtitle">先做可驗證、可追蹤、可解釋的勝平負機率，再逐步擴充資料源、模型績效與模擬競猜。</p>
      </section>

      <section className="grid">
        {fixtures.map((fixture, index) => {
          const prediction = predictions[index];
          return (
            <article className="card" key={fixture.id}>
              <div className="cardTop">
                <span>{fixture.stage}</span>
                <span>{fixture.status}</span>
              </div>
              <h2>{fixture.home_team.name} vs {fixture.away_team.name}</h2>
              <p className="time">{new Date(fixture.kickoff_time).toLocaleString('zh-TW', { timeZone: 'Asia/Taipei' })}</p>

              {prediction ? (
                <>
                  <div className="probabilities">
                    <PercentBar label="主勝" value={prediction.probabilities.home_win} />
                    <PercentBar label="和局" value={prediction.probabilities.draw} />
                    <PercentBar label="客勝" value={prediction.probabilities.away_win} />
                  </div>

                  <div className="metrics">
                    <div>
                      <span>預期進球</span>
                      <strong>{prediction.expected_goals.home} : {prediction.expected_goals.away}</strong>
                    </div>
                    <div>
                      <span>信心</span>
                      <strong>{prediction.confidence}</strong>
                    </div>
                  </div>

                  <div className="scores">
                    {prediction.most_likely_scores.slice(0, 3).map((item) => (
                      <span key={item.score}>{item.score} · {Math.round(item.probability * 100)}%</span>
                    ))}
                  </div>

                  <ul className="reasons">
                    {prediction.explanation.map((item) => <li key={item}>{item}</li>)}
                  </ul>

                  <p className="version">Model: {prediction.model_version}</p>
                </>
              ) : (
                <p className="warning">請先啟動 FastAPI 後端以取得即時預測。</p>
              )}
            </article>
          );
        })}
      </section>
    </main>
  );
}
