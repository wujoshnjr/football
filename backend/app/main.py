from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from app.config import get_settings
from app.schemas import DataSourceStatus, Fixture, ManualPredictionInput, ModelPerformance, TeamSnapshot
from app.services.advanced_feature_registry import advanced_feature_registry
from app.services.feature_table_service import build_match_feature_table
from app.services.prediction_service import PredictionService
from app.services.source_fusion_service import SourceFusionService

settings = get_settings()
app = FastAPI(title=settings.app_name, version=settings.model_version)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def team(
    team_id: str,
    name: str,
    country: str,
    fifa_rank: int | None,
    elo_rating: float,
    recent_points_per_match: float,
    goals_for_per_match: float,
    goals_against_per_match: float,
) -> TeamSnapshot:
    return TeamSnapshot(
        id=team_id,
        name=name,
        country=country,
        fifa_rank=fifa_rank,
        elo_rating=elo_rating,
        recent_points_per_match=recent_points_per_match,
        goals_for_per_match=goals_for_per_match,
        goals_against_per_match=goals_against_per_match,
    )


def demo_fixtures() -> list[Fixture]:
    """Temporary verified fixtures until full live ingestion is enabled.

    Finished matches show scores instead of being treated as upcoming predictions.
    Upcoming matches keep date-only kickoff values when exact kickoff time is not yet
    synced from the live provider.
    """

    argentina = team("arg", "Argentina", "Argentina", 2, 2140, 2.2, 1.9, 0.7)
    algeria = team("alg", "Algeria", "Algeria", 35, 1760, 1.6, 1.4, 1.1)
    japan = team("jpn", "Japan", "Japan", 18, 1845, 2.0, 1.8, 0.9)
    netherlands = team("ned", "Netherlands", "Netherlands", 7, 1995, 1.9, 1.7, 0.8)
    austria = team("aut", "Austria", "Austria", 24, 1840, 1.8, 1.6, 1.0)
    jordan = team("jor", "Jordan", "Jordan", 66, 1585, 1.4, 1.2, 1.4)
    sweden = team("swe", "Sweden", "Sweden", 43, 1780, 1.6, 1.5, 1.1)
    tunisia = team("tun", "Tunisia", "Tunisia", 40, 1730, 1.5, 1.1, 1.0)

    return [
        Fixture(
            id="arg-alg-2026-final",
            home_team=argentina,
            away_team=algeria,
            kickoff_time="2026-06-17T01:00:00Z",
            venue="Kansas City Stadium",
            stage="Group J",
            status="finished",
            home_score=3,
            away_score=0,
        ),
        Fixture(
            id="ned-jpn-2026-final",
            home_team=netherlands,
            away_team=japan,
            kickoff_time="2026-06-14T20:00:00Z",
            venue="Dallas Stadium",
            stage="Group F",
            status="finished",
            home_score=2,
            away_score=2,
        ),
        Fixture(
            id="ned-swe-2026",
            home_team=netherlands,
            away_team=sweden,
            kickoff_time="2026-06-20",
            venue="Houston Stadium",
            stage="Group F",
            status="scheduled",
        ),
        Fixture(
            id="tun-jpn-2026",
            home_team=tunisia,
            away_team=japan,
            kickoff_time="2026-06-20",
            venue="Estadio Monterrey",
            stage="Group F",
            status="scheduled",
        ),
        Fixture(
            id="arg-aut-2026",
            home_team=argentina,
            away_team=austria,
            kickoff_time="2026-06-22",
            venue="Dallas Stadium",
            stage="Group J",
            status="scheduled",
        ),
        Fixture(
            id="jor-alg-2026",
            home_team=jordan,
            away_team=algeria,
            kickoff_time="2026-06-22",
            venue="San Francisco Bay Area Stadium",
            stage="Group J",
            status="scheduled",
        ),
    ]


def source_context():
    return SourceFusionService(settings).build_source_context()


def match_feature_rows():
    return build_match_feature_table(demo_fixtures(), source_context())


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "model_version": settings.model_version}


@app.get("/data-sources", response_model=list[DataSourceStatus])
def data_sources() -> list[DataSourceStatus]:
    return SourceFusionService(settings).registry()


@app.get("/data-sources/context")
def data_source_context():
    return source_context()


@app.get("/model/features")
def model_features():
    return advanced_feature_registry()


@app.get("/model/feature-table")
def model_feature_table():
    return match_feature_rows()


@app.get("/fixtures", response_model=list[Fixture])
def list_fixtures() -> list[Fixture]:
    return demo_fixtures()


@app.get("/fixtures/{fixture_id}", response_model=Fixture)
def get_fixture(fixture_id: str) -> Fixture:
    for fixture in demo_fixtures():
        if fixture.id == fixture_id:
            return fixture
    raise HTTPException(status_code=404, detail="Fixture not found")


@app.get("/predictions/{fixture_id}")
def get_prediction(fixture_id: str):
    fixture = get_fixture(fixture_id)
    if fixture.status.lower() in {"finished", "final", "full_time"}:
        raise HTTPException(status_code=409, detail="Fixture is finished; use final score instead of prediction")
    service = PredictionService(model_version=settings.model_version)
    return service.predict_fixture(fixture, source_context=source_context())


@app.post("/predictions/manual")
def manual_prediction(payload: ManualPredictionInput):
    service = PredictionService(model_version=settings.model_version)
    fixture = Fixture(
        id=payload.fixture_id,
        home_team=payload.home_team,
        away_team=payload.away_team,
        kickoff_time=payload.kickoff_time,
    )
    return service.predict_fixture(fixture, source_context=payload.source_context or source_context())


@app.get("/model/performance", response_model=ModelPerformance)
def model_performance() -> ModelPerformance:
    return ModelPerformance(
        model_version=settings.model_version,
        matches_evaluated=0,
        accuracy=None,
        log_loss=None,
        brier_score=None,
    )
