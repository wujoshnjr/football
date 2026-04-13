import numpy as np
from scipy import stats

class FootballTradingEngine:

    def __init__(self):
        self.simulations = 100000  # ✅ 保留你要求

    def poisson_lambda(self, attack, defense, is_home):
        base = attack * defense * 1.35
        if is_home:
            base *= 1.15  # ✅ 主場優勢
        return max(0.3, min(base, 3.5))

    def simulate_match(self, home_lambda, away_lambda):
        n = self.simulations

        home_goals = np.random.poisson(home_lambda, n)
        away_goals = np.random.poisson(away_lambda, n)

        home_win = np.mean(home_goals > away_goals)
        draw = np.mean(home_goals == away_goals)
        away_win = np.mean(home_goals < away_goals)

        total_goals = home_goals + away_goals

        over25 = np.mean(total_goals > 2.5)

        # Top score
        scores = {}
        for h, a in zip(home_goals[:5000], away_goals[:5000]):
            key = f"{h}-{a}"
            scores[key] = scores.get(key, 0) + 1

        top_scores = sorted(scores.items(), key=lambda x: x[1], reverse=True)[:5]

        return {
            "home_prob": home_win,
            "draw_prob": draw,
            "away_prob": away_win,
            "over25": over25,
            "top_scores": top_scores
        }

    def predict(self, home_team, away_team):
        # ⚠️ 暫時用假資料（下一步會升級成真實API）
        home_attack = np.random.uniform(0.9, 1.3)
        away_attack = np.random.uniform(0.9, 1.3)

        home_defense = np.random.uniform(0.8, 1.2)
        away_defense = np.random.uniform(0.8, 1.2)

        home_lambda = self.poisson_lambda(home_attack, away_defense, True)
        away_lambda = self.poisson_lambda(away_attack, home_defense, False)

        result = self.simulate_match(home_lambda, away_lambda)

        return {
            "home_team": home_team,
            "away_team": away_team,
            "home_lambda": home_lambda,
            "away_lambda": away_lambda,
            **result
        }
