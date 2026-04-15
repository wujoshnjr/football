def edge(p, odds):
    return p * odds - 1

def kelly(p, odds):
    e = edge(p, odds)
    return max(0, e / (odds - 1))
