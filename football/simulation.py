import numpy as np

def monte_carlo(lh, la, sims=5000):
    results = []
    for _ in range(sims):
        h = np.random.poisson(lh)
        a = np.random.poisson(la)
        results.append((h,a))
    return results

def calc_probs(results):
    h = sum(1 for x,y in results if x>y)/len(results)
    d = sum(1 for x,y in results if x==y)/len(results)
    a = sum(1 for x,y in results if x<y)/len(results)
    return h, d, a
