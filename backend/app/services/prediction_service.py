from __future__ import annotations

from dataclasses import dataclass
from math import exp, factorial

from app.schemas import (
    ExpectedGoals,
    Fixture,
    PredictionResponse,
    Probabilities,
    ScorelineProbability,
    TeamSnapshot,
)


@dataclass(frozen=True)
class ModelWeights:
    elo: float = 0.45
    poisson: float = 0.55


class PredictionService:
    def __init__(self, model_version: str, weights: ModelWeights | None = None) -> None:
        self.model_version = model_version
        self.weights = weights or ModelWeights()

    def predict_fixture(self, fixture: Fixture) -> PredictionResponse:
        elo_probs = self._elo_probabilities(fixture.home_team, fixture.away_team)
        expected_goals = self._expected_goals(fixture.home_team, fixture.away_team)
        poisson_probs, scorelines = self._poisson_probabilities(expected_goals.home, expected_goals.away)

        mixed = self._mix_probabilities(elo_probs, poisson_probs)
        confidence = self._confidence(mixed)
        explanation = self._explain(fixture, expected_goals, mixed)

        return PredictionResponse(
            fixture_id=fixture.id,
            match=f"{fixture.home_team.name} vs {fixture.away_team.name}",
            kickoff_time=fixture.kickoff_time,
            probabilities=mixed,
            expected_goals=expected_goals,
            most_likely_scores=scorelines[:5],
            confidence=confidence,
            model_version=self.model_version,
            explanation=explanation,
        )

    def _elo_probabilities(self, home: TeamSnapshot, away: TeamSnapshot) -> Probabilities:
        diff = home.elo_rating - away.elo_rating
        home_strength = 1 / (1 + 10 ** (-diff / 400))
        draw = max(0.18, min(0.31, 0.27 - abs(diff) / 2400))
        remaining = 1 - draw
        home_win = remaining * home_strength
        away_win = remaining * (1 - home_strength)
        return self._normalize(Probabilities(home_win=home_win, draw=draw, away_win=away_win))

    def _expected_goals(self, home: TeamSnapshot, away: TeamSnapshot) -> ExpectedGoals:
        home_attack = max(0.2, home.goals_for_per_match)
        away_attack = max(0.2, away.goals_for_per_match)
        home_defense_allowed = max(0.2, home.goals_against_per_match)
        away_defense_allowed = max(0.2, away.goals_against_per_match)

        elo_adjust_home = 1 + (home.elo_rating - away.elo_rating) / 3000
        elo_adjust_away = 1 + (away.elo_rating - home.elo_rating) / 3000
        form_adjust_home = 1 + (home.recent_points_per_match - away.recent_points_per_match) / 18
        form_adjust_away = 1 + (away.recent_points_per_match - home.recent_points_per_match) / 18

        expected_home = ((home_attack + away_defense_allowed) / 2) * elo_adjust_home * form_adjust_home
        expected_away = ((away_attack + home_defense_allowed) / 2) * elo_adjust_away * form_adjust_away

        return ExpectedGoals(
            home=round(max(0.15, min(expected_home, 4.5)), 3),
            away=round(max(0.15, min(expected_away, 4.5)), 3),
        )

    def _poisson_probabilities(self, home_xg: float, away_xg: float) -> tuple[Probabilities, list[ScorelineProbability]]:
        home_win = 0.0
        draw = 0.0
        away_win = 0.0
        scores: list[ScorelineProbability] = []

        for home_goals in range(0, 7):
            for away_goals in range(0, 7):
                prob = self._poisson(home_goals, home_xg) * self._poisson(away_goals, away_xg)
                if home_goals > away_goals:
                    home_win += prob
                elif home_goals == away_goals:
                    draw += prob
                else:
                    away_win += prob
                scores.append(
                    ScorelineProbability(
                        score=f"{home_goals}-{away_goals}",
                        probability=round(prob, 4),
                    )
                )

        scores.sort(key=lambda item: item.probability, reverse=True)
        return self._normalize(Probabilities(home_win=home_win, draw=draw, away_win=away_win)), scores

    def _poisson(self, goals: int, rate: float) -> float:
        return exp(-rate) * rate**goals / factorial(goals)

    def _mix_probabilities(self, elo: Probabilities, poisson: Probabilities) -> Probabilities:
        return self._normalize(
            Probabilities(
                home_win=(elo.home_win * self.weights.elo) + (poisson.home_win * self.weights.poisson),
                draw=(elo.draw * self.weights.elo) + (poisson.draw * self.weights.poisson),
                away_win=(elo.away_win * self.weights.elo) + (poisson.away_win * self.weights.poisson),
            )
        )

    def _normalize(self, probs: Probabilities) -> Probabilities:
        total = probs.home_win + probs.draw + probs.away_win
        if total <= 0:
            return Probabilities(home_win=0.3333, draw=0.3333, away_win=0.3334)
        return Probabilities(
            home_win=round(probs.home_win / total, 4),
            draw=round(probs.draw / total, 4),
            away_win=round(probs.away_win / total, 4),
        )

    def _confidence(self, probs: Probabilities) -> str:
        top = max(probs.home_win, probs.draw, probs.away_win)
        second = sorted([probs.home_win, probs.draw, probs.away_win], reverse=True)[1]
        margin = top - second
        if top >= 0.62 and margin >= 0.18:
            return "high"
        if top >= 0.48 and margin >= 0.10:
            return "medium"
        return "low"

    def _explain(self, fixture: Fixture, expected_goals: ExpectedGoals, probs: Probabilities) -> list[str]:
        home = fixture.home_team
        away = fixture.away_team
        notes: list[str] = []

        if home.elo_rating > away.elo_rating:
            notes.append(f"{home.name} Elo 較高，基礎戰力略佔優勢。")
        elif away.elo_rating > home.elo_rating:
            notes.append(f"{away.name} Elo 較高，基礎戰力略佔優勢。")
        else:
            notes.append("雙方 Elo 接近，模型會更重視進失球與近期狀態。")

        if home.recent_points_per_match > away.recent_points_per_match:
            notes.append(f"{home.name} 近期場均積分較佳。")
        elif away.recent_points_per_match > home.recent_points_per_match:
            notes.append(f"{away.name} 近期場均積分較佳。")

        notes.append(f"Poisson 模型預估進球：{home.name} {expected_goals.home}，{away.name} {expected_goals.away}。")

        top_label = max(
            [("主勝", probs.home_win), ("和局", probs.draw), ("客勝", probs.away_win)],
            key=lambda item: item[1],
        )[0]
        notes.append(f"綜合 Elo 與 Poisson 後，目前最高機率結果為：{top_label}。")
        return notes
