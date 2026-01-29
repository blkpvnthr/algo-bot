def run(data, params):
    syms = list(data.keys())
    w = 1.0 / len(syms)
    return {"target_weights": {s: w for s in syms}}
