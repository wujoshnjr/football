from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from app.config import get_settings
from app.schemas import Fixture, ManualPredictionInput, ModelPerformance, TeamSnapshot
from app.services.prediction_service import PredictionService

settings = get_settings()
app = FastAPI(title=settings.app_name, version=settings.model_version)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def demo_fixtures() -> list[Fixture]:
    argentina = TeamSnapshot(
        id="arg",
        name="Argentina",
        country="Argentina",
        fifa_rank=1,
        elo_rating=2140,
        recent_points_per_match=2.2,
        goals_for_per_match=1.9,
        goals_against_per_match=0.7,
    )
    algeria = TeamSnapshot(
        id="alg",
        name="Algeria",
        country="Algeria",
        fifa_rank=37,
        elo_rating=1760,
        recent_points_per_match=1.6,
        goals_for_per_match=1.4,
        goals_against_per_match=1.1,
    )
    japan = TeamSnapshot(
        id="jpn",
        name="Japan",
        country="Japan",
        fifa_rank=18,
        elo_rating=1845,
        recent_points_per_match=2.0,
        goals_for_per_match=1.8,
        goals_against_per_match=0.9,
    )
    netherlands = TeamSnapshot(
        id="ned",
        name="Netherlands",
        country="Netherlands",
        fifa_rank=7,
        elo_rating=1995,
        recent_points_per_match=1.9,
        goals_for_per_match=1.7,
        goals_against_per_match=0.8,
    )
    return [
        Fixture(
            id="demo-arg-alg-2026",
            home_team=argentina,
            away_team=algeria,
            kickoff_time="2026-06-17T01:00:00Z",
            venue="TBD",
            stage="Group Stage",
        ),
        Fixture(
            id="demo-ned-jpn-2026",
            home_team=netherlands,
            away_team=japan,
            kickoff_time="2026-06-14T20:00:00Z",
            venue="TBD",
            stage="Group Stage",
        ),
    ]


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "model_version": settings.model_version}


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
    service = PredictionService(model_version=settings.model_version)
    return service.predict_fixture(get_fixture(fixture_id))


@app.post("/predictions/manual")
def manual_prediction(payload: ManualPredictionInput):
    service = PredictionService(model_version=settings.model_version)
    fixture = Fixture(
        id=payload.fixture_id,
        home_team=payload.home_team,
        away_team=payload.away_team,
        kickoff_time=payload.kickoff_time,
    )
    return service.predict_fixture(fixture)


@app.get("/model/performance", response_model=ModelPerformance)
def model_performance() -> ModelPerformance:
    return ModelPerformance(
        model_version=settings.model_version,
        matches_evaluated=0,
        accuracy=None,
        log_loss=None,
        brier_score=None,
    )
