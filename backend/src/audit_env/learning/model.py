"""A small, dependency-free logistic-regression detector (one binary head per issue type and candidate kind).

Pure Python on purpose: it trains in seconds on 2 CPUs, runs inside the offline
container next to the stdlib-only core, and is deterministic. Its only source of
randomness is an explicit ``random.Random(seed)`` used to shuffle the training
order; floats are rounded when saved so the JSON is stable to read and diff.
"""

from __future__ import annotations

import json
import math
import random
from pathlib import Path

from .features import FEATURES, HEADS

FORMAT = "audit-env/learned-auditor/1"
DEFAULT_PATH = Path(__file__).with_name("learned_auditor.json")


def _sigmoid(z: float) -> float:
    z = max(-30.0, min(30.0, z))
    return 1.0 / (1.0 + math.exp(-z))


def _round(v: float) -> float:
    return float(f"{v:.6g}")


class Detector:
    def __init__(self, params: dict):
        if params.get("format") != FORMAT:
            raise ValueError("not a learned-auditor model file")
        self.params = params
        self.threshold = params["threshold"]

    # ----------------------------------------------------------------- inference

    def scores(self, candidate) -> dict:
        p = self.params["kinds"][candidate.kind]
        z = [(v - m) / s for v, m, s in zip(candidate.x, p["mean"], p["scale"], strict=True)]
        out = {}
        for head, h in p["heads"].items():
            out[head] = _sigmoid(h["bias"] + sum(w * v for w, v in zip(h["weights"], z, strict=True)))
        return out

    # ----------------------------------------------------------------- persistence

    @classmethod
    def load(cls, path: Path | str = DEFAULT_PATH) -> "Detector":
        return cls(json.loads(Path(path).read_text()))

    def dumps(self) -> str:
        return json.dumps(self.params, indent=2, sort_keys=True) + "\n"


def fit(samples: dict, *, seed: int = 0, epochs: int = 25, lr: float = 0.3, l2: float = 1e-4) -> dict:
    """Train every head. ``samples[kind]`` is a list of (x, y) with y = {head: 0/1}.

    Returns the ``kinds`` section of a model file (standardisation + weights).
    """
    rng = random.Random(seed)
    kinds = {}
    for kind in sorted(HEADS):
        rows = samples.get(kind, [])
        n_feat = len(FEATURES[kind])
        mean = [0.0] * n_feat
        scale = [1.0] * n_feat
        if rows:
            for j in range(n_feat):
                col = [x[j] for x, _ in rows]
                mu = sum(col) / len(col)
                var = sum((v - mu) ** 2 for v in col) / len(col)
                mean[j], scale[j] = mu, (math.sqrt(var) if var > 1e-12 else 1.0)
        z_rows = [([(v - m) / s for v, m, s in zip(x, mean, scale, strict=True)], y) for x, y in rows]
        heads = {}
        for head in HEADS[kind]:
            w = [0.0] * n_feat
            b = 0.0
            order = list(range(len(z_rows)))
            for epoch in range(epochs):
                rng.shuffle(order)
                step = lr / (1 + epoch)
                for i in order:
                    z, y = z_rows[i]
                    g = _sigmoid(b + sum(wj * zj for wj, zj in zip(w, z, strict=True))) - y[head]
                    b -= step * g
                    for j in range(n_feat):
                        w[j] -= step * (g * z[j] + l2 * w[j])
            heads[head] = {"bias": _round(b), "weights": [_round(v) for v in w]}
        kinds[kind] = {
            "features": list(FEATURES[kind]),
            "mean": [_round(v) for v in mean],
            "scale": [_round(v) for v in scale],
            "heads": heads,
        }
    return kinds
