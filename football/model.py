import numpy as np
from scipy.stats import poisson

class TeamModel:
    def __init__(self):
        self.attack = {}
        self.defense = {}
        self.home_adv = 0.2

    def train(self, matches):
        for m in matches:
            h = m['home']
            a = m['away']
            hg = m['home_goals']
            ag = m['away_goals']

            self.attack[h] = self.attack.get(h, 1) + hg * 0.05
            self.defense[h] = self.defense.get(h, 1) + ag * 0.05

            self.attack[a] = self.attack.get(a, 1) + ag * 0.05
            self.defense[a] = self.defense.get(a, 1) + hg * 0.05

    def predict_lambda(self, home, away):
        lh = np.exp(self.attack.get(home,1) - self.defense.get(away,1) + self.home_adv)
        la = np.exp(self.attack.get(away,1) - self.defense.get(home,1))
        return lh, la


def build_matrix(lh, la):
    matrix = np.zeros((6,6))
    for i in range(6):
        for j in range(6):
            matrix[i,j] = poisson.pmf(i, lh) * poisson.pmf(j, la)
    return matrix / matrix.sum()
