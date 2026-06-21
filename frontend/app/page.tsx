export const dynamic = 'force-dynamic';
export const revalidate = 0;
export const fetchCache = 'force-no-store';

type ProductFixture = {
  id: string;
  fixture_id: string;
  home_team: string;
  away_team: string;
  kickoff_time: string;
  kickoff_time_taiwan?: string | null;
  venue?: string | null;
  stage: string;
  status: string;
  home_score?: number | null;
  away_score?: number | null;
  winner?: string | null;
  result?: string | null;
  finalized_at?: string | null;
  source_provenance?: Array<{ source_key?: string | null; role?: string | null }>;
  source_keys?: string[];
  last_updated_at?: string | null;
};

type DataCompleteness = {
  cache_exists: boolean;
  cache_path?: string | null;
  fixture_count: number;
  completed_count: number;
  tomorrow_count: number;
  scheduled_count: number;
  is_complete_worldcup_schedule: boolean;
  missing_reason?: string | null;
  source_used: string;
  expected_fixture_count?: number;
  minimum_fixture_count?: number;
};

type FixturePayload = {
  generated_at?: string | null;
  timezone: string;
  source_used: string;
  fixture_count: number;
  fixtures: ProductFixture[];
  data_completeness: DataCompleteness;
  warnings?: string[];
  cache_path?: string | null;
};

type Forecast = {
  probabilities: { home_win: number; draw: number; away_win: number };
  expected_goals: { home: number; away: number };
  confidence: string;
  model_version: string;
  explanation: string[];
};

type FetchResult<T> = { data: T; ok: boolean; error?: string };

const API_BASE_URL = process.env.NEXT_PUBLIC_API_BASE_URL || 'http://localhost:8000';
const requestTimeoutMs = 6500;
const predictionFetchLimit = 3;

function emptyFixturePayload(label: string): FixturePayload {
  return {
    timezone: 'Asia/Taipei',
    source_used: label,
    fixture_count: 0,
    fixtures: [],
    data_completeness: {
      cache_exists: false,
      cache_path: null,
      fixture_count: 0,
      completed_count: 0,
      tomorrow_count: 0,
      scheduled_count: 0,
      is_complete_worldcup_schedule: false,
      missing_reason: 'frontend_fetch_failed',
      source_used: label,
    },
    warnings: ['Render 可能冷啟動，或 backend fixture API 暫時無回應。'],
    cache_path: null,
  };
}

function isCompleted(fixture: ProductFixture) {
  return fixture.status === 'completed' || ['finished', 'final', 'full_time'].includes(fixture.status.toLowerCase());
}

function percent(value: number) {
  return `${Math.round(value * 100)}%`;
}

function taiwanDateKeyFromDate(value: Date) {
  const parts = new Intl.DateTimeFormat('en-US', {
    timeZone: 'Asia/Taipei',
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
  }).formatToParts(value);
  const year = parts.find((part) => part.type === 'year')?.value ?? '0000';
  const month = parts.find((part) => part.type === 'month')?.value ?? '01';
  const day = parts.find((part) => part.type === 'day')?.value ?? '01';
  return `${year}-${month}-${day}`;
}

function tomorrowTaiwanDateKey() {
  const todayKey = taiwanDateKeyFromDate(new Date());
  const taiwanMidnight = new Date(`${todayKey}T00:00:00+08:00`);
  taiwanMidnight.setUTCDate(taiwanMidnight.getUTCDate() + 1);
  return taiwanDateKeyFromDate(taiwanMidnight);
}

function fixtureTaiwanDateKey(fixture: ProductFixture) {
  const raw = fixture.kickoff_time_taiwan ?? fixture.kickoff_time;
  if (!raw || raw === 'unknown') return null;
  if (/^\d{4}-\d{2}-\d{2}$/.test(raw)) return raw;
  const parsed = new Date(raw);
  if (Number.isNaN(parsed.getTime())) return null;
  return taiwanDateKeyFromDate(parsed);
}

function displayTime(value?: string | null) {
  if (!value || value === 'unknown') return '時間待定';
  if (/^\d{4}-\d{2}-\d{2}$/.test(value)) return value.replaceAll('-', '/');
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) return value;
  return parsed.toLocaleString('zh-TW', {
    timeZone: 'Asia/Taipei',
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
    hour12: false,
  });
}

function sourceBadges(fixture: ProductFixture) {
  const keys = fixture.source_keys?.length
    ? fixture.source_keys
    : fixture.source_provenance?.map((item) => item.source_key).filter(Boolean) ?? [];
  return Array.from(new Set(keys)).slice(0, 3);
}

function diagnosticMessage(result: FetchResult<unknown>) {
  if (result.ok) return '連線正常';
  if (result.error?.includes('timeout')) return 'Render 可能冷啟動，請稍後重試。';
  return result.error ?? 'Render 可能冷啟動，或後端暫時無回應。';
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
      ? `timeout after ${timeoutMs}ms; Render 可能冷啟動`
      : error instanceof Error ? error.message : 'unknown error';
    return { data: fallback, ok: false, error: message };
  } finally {
    clearTimeout(timer);
  }
}

async function getForecast(fixture: ProductFixture): Promise<Forecast | null> {
  if (isCompleted(fixture)) return null;
  const result = await getJson<Forecast | null>(`/predictions/${fixture.fixture_id}?source=auto`, null, 3500);
  return result.ok ? result.data : null;
}

function CompletenessNotice({ payload }: { payload: FixturePayload }) {
  const completeness = payload.data_completeness;
  if (completeness.is_complete_worldcup_schedule) {
    return <p className="notice good">資料完整度：完整世界盃賽程 cache 已載入。</p>;
  }
  return (
    <div className="notice warn">
      <strong>{payload.source_used === 'demo_fallback' ? 'Demo fallback，不是正式資料' : '資料仍在同步'}</strong>
      <span>cache exists：{completeness.cache_exists ? 'yes' : 'no'}</span>
      <span>目前 cache 賽事數：{completeness.fixture_count}</span>
      <span>原因：{completeness.missing_reason ?? 'unknown'}</span>
      <span>更新指令：python scripts/build_worldcup_fixture_cache.py</span>
    </div>
  );
}

function ForecastSummary({ forecast }: { forecast: Forecast | null }) {
  if (!forecast) {
    return <p className="aiSummary">AI 預測摘要：待產生，或後端模型 / Render 冷啟動暫時未回應。</p>;
  }
  return (
    <div className="aiSummary">
      <strong>AI 預測摘要</strong>
      <span>主勝 {percent(forecast.probabilities.home_win)} · 和局 {percent(forecast.probabilities.draw)} · 客勝 {percent(forecast.probabilities.away_win)}</span>
      <span>預期進球 {forecast.expected_goals.home} : {forecast.expected_goals.away} · 信心 {forecast.confidence}</span>
    </div>
  );
}

function FixtureCard({ fixture, forecast, compact = false }: { fixture: ProductFixture; forecast?: Forecast | null; compact?: boolean }) {
  const completed = isCompleted(fixture);
  const badges = sourceBadges(fixture);
  return (
    <article className={compact ? 'card fixtureCard compact' : 'card fixtureCard'}>
      <div className="cardTop">
        <span>{fixture.stage}</span>
        <span>{completed ? '已完賽' : fixture.status === 'live' ? '進行中' : '未開賽'}</span>
      </div>
      <h2>{fixture.home_team} vs {fixture.away_team}</h2>
      <p className="time">台灣時間：{displayTime(fixture.kickoff_time_taiwan ?? fixture.kickoff_time)}</p>
      {fixture.venue ? <p className="time">球場：{fixture.venue}</p> : null}
      {completed ? (
        <div className="scoreLine">
          <strong>{fixture.home_score ?? '-'} : {fixture.away_score ?? '-'}</strong>
          <span>{fixture.result ?? 'result pending'}</span>
        </div>
      ) : (
        <ForecastSummary forecast={forecast ?? null} />
      )}
      <div className="badgeRow">
        {badges.length > 0 ? badges.map((badge) => <span key={badge}>{badge}</span>) : <span>{fixture.source_provenance?.length ? 'source_provenance' : 'source pending'}</span>}
      </div>
      {fixture.last_updated_at ? <p className="version">更新：{displayTime(fixture.last_updated_at)}</p> : null}
    </article>
  );
}

function SectionEmpty({ title, detail }: { title: string; detail: string }) {
  return <div className="emptyState"><h2>{title}</h2><p>{detail}</p></div>;
}

export default async function HomePage() {
  const scheduleResult = await getJson<FixturePayload>(
    '/fixtures?status=all&tz=Asia/Taipei',
    emptyFixturePayload('schedule_fetch_failed'),
  );

  const schedulePayload = scheduleResult.data;
  const completeness = schedulePayload.data_completeness;
  const tomorrowKey = tomorrowTaiwanDateKey();
  const tomorrowFixtures = schedulePayload.fixtures.filter((fixture) => fixtureTaiwanDateKey(fixture) === tomorrowKey);
  const completedSchedule = schedulePayload.fixtures.filter(isCompleted);
  const upcomingSchedule = schedulePayload.fixtures.filter((fixture) => !isCompleted(fixture));
  const tomorrowPredictionTargets = tomorrowFixtures.filter((fixture) => !isCompleted(fixture)).slice(0, predictionFetchLimit);
  const forecastPairs = await Promise.all(tomorrowPredictionTargets.map(async (fixture) => [fixture.fixture_id, await getForecast(fixture)] as const));
  const forecastByFixture = new Map(forecastPairs);

  return (
    <main className="page">
      <nav className="topbar">
        <div className="brand"><span>WC26</span> Match Center</div>
        <div className="navlinks"><a href="#tomorrow">明日賽事</a><a href="#completed">已完賽</a><a href="#schedule">完整賽程</a><a href="#diagnostics">Diagnostics</a></div>
      </nav>

      <section className="hero matchHero">
        <p className="eyebrow">2026 FIFA World Cup</p>
        <h1>2026 世界盃比賽中心</h1>
        <p className="subtitle">明日賽程、完賽比分、完整 fixture cache 與資料來源透明度集中在同一頁。首頁只讀一次 fixture payload，再在前端分出明日、已完賽與完整賽程，降低 Render 冷啟動 timeout 風險。</p>
        <div className="metrics heroMetrics">
          <div><span>總賽事數</span><strong>{completeness.fixture_count}</strong></div>
          <div><span>已完賽</span><strong>{completeness.completed_count}</strong></div>
          <div><span>明日賽事</span><strong>{tomorrowFixtures.length}</strong></div>
          <div><span>資料完整度</span><strong>{completeness.is_complete_worldcup_schedule ? '完整' : '同步中'}</strong></div>
        </div>
        <CompletenessNotice payload={schedulePayload} />
      </section>

      <section className="section" id="tomorrow">
        <div className="sectionHead"><p>Tomorrow</p><h2>明日全部比賽</h2><span>由單次 /fixtures payload 在前端篩選，不額外 fetch fixture endpoints</span></div>
        {tomorrowFixtures.length > 0 ? (
          <div className="spotlight matchGrid">
            {tomorrowFixtures.map((fixture) => <FixtureCard key={fixture.fixture_id} fixture={fixture} forecast={forecastByFixture.get(fixture.fixture_id) ?? null} />)}
          </div>
        ) : <SectionEmpty title="明日賽程尚未載入" detail="若資料來源仍在同步，請執行 fixture cache builder；Demo fallback 不會偽裝成完整賽程。" />}
      </section>

      <section className="section" id="completed">
        <div className="sectionHead"><p>Results</p><h2>已完賽結果</h2><span>從主賽程 payload 篩出，保留比分、勝負、來源與 finalized_at</span></div>
        {completedSchedule.length > 0 ? (
          <div className="grid resultGrid">
            {completedSchedule.map((fixture) => <FixtureCard key={fixture.fixture_id} fixture={fixture} compact />)}
          </div>
        ) : <SectionEmpty title="尚無已完賽資料" detail="目前 cache 沒有 completed fixtures；若只看到 demo fallback，頁面會明確標示資料不完整。" />}
      </section>

      <section className="section" id="schedule">
        <div className="sectionHead"><p>Schedule</p><h2>完整賽程</h2><span>completed / upcoming 分區，依日期排序</span></div>
        <div className="splitSchedule">
          <div>
            <h3>Upcoming</h3>
            {upcomingSchedule.length > 0 ? upcomingSchedule.map((fixture) => <FixtureCard key={fixture.fixture_id} fixture={fixture} compact />) : <p className="warning">沒有 upcoming fixtures。</p>}
          </div>
          <div>
            <h3>Completed</h3>
            {completedSchedule.length > 0 ? completedSchedule.map((fixture) => <FixtureCard key={fixture.fixture_id} fixture={fixture} compact />) : <p className="warning">沒有 completed fixtures。</p>}
          </div>
        </div>
      </section>

      <section className="section diagnosticsSection" id="diagnostics">
        <div className="sectionHead"><p>Diagnostics</p><h2>Runtime Diagnostics</h2><span>工程狀態保留在底部</span></div>
        <div className="diagnosticGrid">
          <div className="panel"><p className="eyebrow">Backend</p><h2>Fixture API</h2><span className={scheduleResult.ok ? 'chip ok' : 'chip bad'}>{diagnosticMessage(scheduleResult)}</span><p className="time">API Base：{API_BASE_URL}</p></div>
          <div className="panel"><p className="eyebrow">Cache</p><h2>Runtime Fixture Cache</h2><span className={completeness.cache_exists ? 'chip ok' : 'chip bad'}>{completeness.cache_exists ? 'cache exists' : 'cache missing'}</span><p className="time">source：{schedulePayload.source_used}</p><p className="time">cache：{schedulePayload.cache_path ?? completeness.cache_path ?? 'not available'}</p></div>
          <div className="panel"><p className="eyebrow">Completeness</p><h2>Schedule Quality</h2><span className={completeness.is_complete_worldcup_schedule ? 'chip ok' : 'chip bad'}>{completeness.is_complete_worldcup_schedule ? '完整' : '同步中'}</span><p className="time">missing_reason：{completeness.missing_reason ?? 'none'}</p><p className="time">Render 可能冷啟動時，首頁仍會保留 fallback JSON 狀態。</p></div>
        </div>
      </section>

      <footer className="footer">World Cup Match Center — AI predictions are informational analysis only. No live betting, no wagering, no stake sizing.</footer>
    </main>
  );
}
