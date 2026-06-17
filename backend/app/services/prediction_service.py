from __future__ import annotations

from dataclasses import dataclass
from math import exp, factorial
from typing import Any

from app.schemas import (
    ExpectedGoals,
    Fixture,
    PredictionDiagnostics,
    PredictionResponse,
    Probabilities,
    ProbabilityComponent,
    ScorelineProbability,
    SourceFeatureBundle,
    TeamSnapshot,
)


@dataclass(frozen=True)
class ModelWeights:
    elo: float = 0.32
    poisson: float = 0.48
    market: float = 0.20


class PredictionService:
    def __init__(self, model_version: str, weights: ModelWeights | None = None) -> None:
        self.model_version = model_version
        self.weights = weights or ModelWeights()

    def predict_fixture(
        self,
        fixture: Fixture,
        source_context: SourceFeatureBundle | None = None,
        market_signal: dict[str, Any] | None = None,
    ) -> PredictionResponse:
        elo_probs = self._elo_probabilities(fixture.home_team, fixture.away_team)
        expected_goals = self._expected_goals(fixture.home_team, fixture.away_team)
        poisson_probs, scorelines = self._poisson_probabilities(expected_goals.home, expected_goals.away)
        market_probs = self._market_probabilities(market_signal)

        components = self._components(elo_probs, poisson_probs, market_probs, market_signal)
        mixed = self._mix_components(components)
        mixed = self._apply_source_context(mixed, source_context)
        diagnostics = self._diagnostics(components, mixed, source_context, market_signal)
        confidence = self._confidence(mixed, source_context, diagnostics)
        explanation = self._explain(fixture, expected_goals, mixed, source_context, diagnostics)

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
            source_context=source_context,
            diagnostics=diagnostics,
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

    def _market_probabilities(self, market_signal: dict[str, Any] | None) -> Probabilities | None:
        if not market_signal or not market_signal.get("market_signal_available"):
            return None
        home = market_signal.get("market_home_implied_probability")
        draw = market_signal.get("market_draw_implied_probability")
        away = market_signal.get("market_away_implied_probability")
        if not all(isinstance(value, (int, float)) for value in [home, draw, away]):
            return None
        return self._normalize(Probabilities(home_win=float(home), draw=float(draw), away_win=float(away)))

    def _components(
        self,
        elo: Probabilities,
        poisson: Probabilities,
        market: Probabilities | None,
        market_signal: dict[str, Any] | None,
    ) -> list[ProbabilityComponent]:
        components = [
            ProbabilityComponent(name="elo_rating", weight=self.weights.elo, probabilities=elo, notes="Team strength baseline."),
            ProbabilityComponent(name="poisson_goals", weight=self.weights.poisson, probabilities=poisson, notes="Goal-rate baseline from attack, defense, form, and rating."),
        ]
        if market is not None:
            components.append(
                ProbabilityComponent(
                    name="market_consensus",
                    weight=self.weights.market,
                    probabilities=market,
                    notes=f"The Odds API h2h consensus from {market_signal.get('market_bookmaker_count', 0)} bookmaker prices.",
                )
            )
        return components

    def _mix_components(self, components: list[ProbabilityComponent]) -> Probabilities:
        active = [component for component in components if component.active and component.weight > 0]
        total_weight = sum(component.weight for component in active)
        if total_weight <= 0:
            return Probabilities(home_win=0.3333, draw=0.3333, away_win=0.3334)
        home = sum(component.probabilities.home_win * component.weight for component in active) / total_weight
        draw = sum(component.probabilities.draw * component.weight for component in active) / total_weight
        away = sum(component.probabilities.away_win * component.weight for component in active) / total_weight
        return self._normalize(Probabilities(home_win=home, draw=draw, away_win=away))

    def _apply_source_context(self, probs: Probabilities, source_context: SourceFeatureBundle | None) -> Probabilities:
        if source_context is None or source_context.reliability_score <= 0:
            return probs

        reliability = source_context.reliability_score
        consensus = source_context.fixture_consensus_score
        if consensus <= 0:
            return probs

        top_label, _ = max(
            [("home", probs.home_win), ("draw", probs.draw), ("away", probs.away_win)],
            key=lambda item: item[1],
        )
        nudge = min(0.025, reliability * consensus * 0.03)
        adjusted = {
            "home": probs.home_win,
            "draw": probs.draw,
            "away": probs.away_win,
        }
        adjusted[top_label] += nudge
        for key in adjusted:
            if key != top_label:
                adjusted[key] = max(0.01, adjusted[key] - nudge / 2)
        return self._normalize(
            Probabilities(
                home_win=adjusted["home"],
                draw=adjusted["draw"],
                away_win=adjusted["away"],
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

    def _diagnostics(
        self,
        components: list[ProbabilityComponent],
        probs: Probabilities,
        source_context: SourceFeatureBundle | None,
        market_signal: dict[str, Any] | None,
    ) -> PredictionDiagnostics:
        risk_flags: list[str] = []
        reason_codes: list[str] = []
        top = max(probs.home_win, probs.draw, probs.away_win)
        second = sorted([probs.home_win, probs.draw, probs.away_win], reverse=True)[1]
        if top - second < 0.08:
            risk_flags.append("low_margin_between_top_outcomes")
        if source_context and source_context.reliability_score < 0.45:
            risk_flags.append("low_source_reliability")
        if not market_signal or not market_signal.get("market_signal_available"):
            risk_flags.append("market_signal_missing")
        if any(component.name == "market_consensus" for component in components):
            reason_codes.append("market_consensus_blended")
        reason_codes.extend(["elo_rating_baseline", "poisson_goal_model", "source_reliability_adjustment"])
        return PredictionDiagnostics(
            components=components,
            market_signal_used=any(component.name == "market_consensus" for component in components),
            calibration_status="needs_backtest_calibration",
            risk_flags=risk_flags,
            reason_codes=reason_codes,
        )

    def _confidence(
        self,
        probs: Probabilities,
        source_context: SourceFeatureBundle | None = None,
        diagnostics: PredictionDiagnostics | None = None,
    ) -> str:
        top = max(probs.home_win, probs.draw, probs.away_win)
        second = sorted([probs.home_win, probs.draw, probs.away_win], reverse=True)[1]
        margin = top - second
        reliability = source_context.reliability_score if source_context else 0.0
        risk_count = len(diagnostics.risk_flags) if diagnostics else 0
        if top >= 0.62 and margin >= 0.18 and reliability >= 0.45 and risk_count <= 1:
            return "high"
        if top >= 0.48 and margin >= 0.10 and risk_count <= 2:
            return "medium"
        return "low"

    def _explain(
        self,
        fixture: Fixture,
        expected_goals: ExpectedGoals,
        probs: Probabilities,
        source_context: SourceFeatureBundle | None = None,
        diagnostics: PredictionDiagnostics | None = None,
    ) -> list[str]:
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

        if source_context:
            notes.append(
                f"資料源融合：已配置 {len(source_context.sources_configured)} 個來源，實際使用 {len(source_context.sources_used)} 個來源，可靠度 {source_context.reliability_score:.2f}。"
            )
            notes.append(source_context.model_adjustment_note)

        if diagnostics and diagnostics.market_signal_used:
            notes.append("The Odds API 市場共識已納入模型混合，但只作為分析訊號，不作下注執行。")
        elif diagnostics:
            notes.append("市場共識尚未匹配，本次預測以 Elo、Poisson 與資料源可靠度為主。")

        top_label = max(
            [("主勝", probs.home_win), ("和局", probs.draw), ("客勝", probs.away_win)],
            key=lambda item: item[1],
        )[0]
        notes.append(f"綜合 Elo、Poisson、資料源可靠度與可用市場訊號後，目前最高機率結果為：{top_label}。")
        return notes
