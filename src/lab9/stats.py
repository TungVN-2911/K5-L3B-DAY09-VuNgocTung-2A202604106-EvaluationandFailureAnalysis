"""Statistics students implement (M2 judge calibration, M4 paired bootstrap).

Rules: a judge is a classifier -- measure it like one. A higher mean is not
"better" until the paired CI of the difference excludes 0.
Reference values to self-check are in tests/test_lab9_stats.py.
"""

from __future__ import annotations

import math
from collections.abc import Sequence

import numpy as np
from scipy import stats as scipy_stats

POS = "FAIL"   # the judge's job is to FIND failures, so FAIL is the positive class


def _norm(labels: Sequence[str]) -> list[str]:
    return [str(x).strip().upper() for x in labels]


def confusion(human: Sequence[str], judge: Sequence[str]) -> dict[str, int]:
    """tp/fp/fn/tn with FAIL as positive."""
    h, j = _norm(human), _norm(judge)
    if len(h) != len(j):
        raise ValueError(f"length mismatch: {len(h)} human vs {len(j)} judge labels")
    cm = {"tp": 0, "fp": 0, "fn": 0, "tn": 0}
    for hv, jv in zip(h, j):
        if jv == POS:
            cm["tp" if hv == POS else "fp"] += 1
        else:
            cm["fn" if hv == POS else "tn"] += 1
    return cm


def precision_recall(human: Sequence[str], judge: Sequence[str]) -> tuple[float, float]:
    cm = confusion(human, judge)
    p_den, r_den = cm["tp"] + cm["fp"], cm["tp"] + cm["fn"]
    return (cm["tp"] / p_den if p_den else 0.0, cm["tp"] / r_den if r_den else 0.0)


def cohen_kappa(human: Sequence[str], judge: Sequence[str]) -> float:
    """kappa = (p_o - p_e) / (1 - p_e). Raise ValueError when undefined (p_e == 1):
    a constant judge has no signal and must FAIL calibration, not pass on a technicality."""
    cm = confusion(human, judge)
    n = sum(cm.values())
    if n == 0:
        raise ValueError("kappa undefined: no labels")
    p_o = (cm["tp"] + cm["tn"]) / n
    h_pos, j_pos = (cm["tp"] + cm["fn"]) / n, (cm["tp"] + cm["fp"]) / n
    p_e = h_pos * j_pos + (1 - h_pos) * (1 - j_pos)
    if math.isclose(p_e, 1.0):
        raise ValueError("kappa undefined: chance agreement p_e == 1 (constant labels)")
    return (p_o - p_e) / (1 - p_e)


def rogan_gladen(observed_rate: float, sensitivity: float, specificity: float) -> float:
    """Correct an observed failure rate for judge error; clip to [0, 1].
    Returns NaN when sens + spec <= 1: a judge no better than chance cannot be corrected."""
    den = sensitivity + specificity - 1
    if den <= 0:
        return float("nan")
    return min(1.0, max(0.0, (observed_rate + specificity - 1) / den))


def paired_bootstrap(a: Sequence[float], b: Sequence[float], *, n_resamples: int = 1000,
                     rng: int = 2027, confidence: float = 0.95) -> tuple[float, float, float]:
    """a[i], b[i] = per-item mean over seeds, SAME items, SAME order.
    Return (mean(a)-mean(b), lo, hi) with scipy.stats.bootstrap(paired=True, method="percentile",
    rng=numpy.random.default_rng(rng)). If a == b everywhere return (0.0, 0.0, 0.0)."""
    x, y = np.asarray(a, dtype=float), np.asarray(b, dtype=float)
    if x.shape != y.shape:
        raise ValueError(f"paired samples need equal length: {len(x)} vs {len(y)}")
    if x.size == 0:
        raise ValueError("paired_bootstrap needs at least one item")
    if np.array_equal(x, y):
        return (0.0, 0.0, 0.0)
    diff = float(x.mean() - y.mean())
    if x.size == 1:   # one item: no resampling variance to speak of
        return (diff, diff, diff)
    res = scipy_stats.bootstrap((x, y), lambda u, v, axis=-1: u.mean(axis=axis) - v.mean(axis=axis),
                                paired=True, vectorized=True, n_resamples=n_resamples,
                                confidence_level=confidence, method="percentile",
                                rng=np.random.default_rng(rng))
    return (diff, float(res.confidence_interval.low), float(res.confidence_interval.high))


def pass_at_k(n: int, c: int, k: int) -> float:
    """Probability that AT LEAST ONE of k trials drawn from n (c of them passing) passes.
    Unbiased estimator (Chen et al. 2021): 1 - C(n-c, k) / C(n, k). Raise ValueError if k > n."""
    # TODO M6
    raise NotImplementedError


def pass_hat_k(n: int, c: int, k: int) -> float:
    """pass^k (tau-bench, Yao et al. 2024): probability that ALL k trials drawn from n pass.
    Unbiased estimator: C(c, k) / C(n, k). Raise ValueError if k > n.
    pass^k <= pass@1 <= pass@k; a reliable agent keeps pass^k close to pass@1."""
    # TODO M6
    raise NotImplementedError
