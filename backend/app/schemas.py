from pydantic import BaseModel, Field


class TeamSnapshot(BaseModel):
    id: str
    name: str
    country: str
    fifa_rank: int | None = None
    elo_rating: float = 1500.0
    recent_points_per_match: float = 1.5
    goals_for_per_match: float = 1.2
    goals_against_per_match: float = 1.2


class Fixture(BaseModel):
    id: str
    home_team: TeamSnapshot
    away_team: TeamSnapshot
    kickoff_time: str
    venue: str | None = None
    stage: str = "Group Stage"
    status: str = "scheduled"
    home_score: int | None = None
    away_score: int | None = None


class Probabilities(BaseModel):
    home_win: float = Field(ge=0, le=1)
    draw: float = Field(ge=0, le=1)
    away_win: float = Field(ge=0, le=1)


class ExpectedGoals(BaseModel):
    home: float
    away: float


class ScorelineProbability(BaseModel):
    score: str
    probability: float


class PredictionResponse(BaseModel):
    fixture_id: str
    match: str
    kickoff_time: str
    probabilities: Probabilities
    expected_goals: ExpectedGoals
    most_likely_scores: list[ScorelineProbability]
    confidence: str
    model_version: str
    explanation: list[str]


class ManualPredictionInput(BaseModel):
    fixture_id: str = "manual"
    home_team: TeamSnapshot
    away_team: TeamSnapshot
    kickoff_time: str = "TBD"


class ModelPerformance(BaseModel):
    model_version: str
    matches_evaluated: int
    accuracy: float | None = None
    log_loss: float | None = None
    brier_score: float | None = None
