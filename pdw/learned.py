"""Learned baselines (logistic regression, gradient-boosted trees) on the same signals.

Features per step: the five indicators and their change over the last W steps (10
features). Label: a primary unsafe onset occurs within the next H_max steps. Only safe,
unmasked steps are used, so the learned models face exactly the task the rule-based
score faces. Models are trained on even tuning seeds only; thresholds are then tuned on
odd tuning seeds, and everything is reported on the test seeds.
"""

from __future__ import annotations

import numpy as np

LEARNED = ("logreg", "gbt")


def features(ind: np.ndarray, window: int = 10) -> np.ndarray:
    ind = np.asarray(ind, dtype=np.float32)
    lagged = np.vstack([np.repeat(ind[:1], min(window, len(ind)), axis=0), ind])[: len(ind)]
    return np.hstack([ind, ind - lagged])


def labels(T: int, events: np.ndarray, H_max: int = 20, H_min: int = 1) -> np.ndarray:
    """y[t] = 1 if some event onset d satisfies t + H_min <= d <= t + H_max."""
    y = np.zeros(T, bool)
    for d in np.asarray(events, dtype=np.int64):
        y[max(0, d - H_max): max(0, d - H_min + 1)] = True
    return y


def fit(X: np.ndarray, y: np.ndarray, prior: float, seed: int = 0) -> dict:
    """Fit both models on a class-balanced sample. `prior` is the true share of positive
    steps (measured before balancing); scores are corrected back to it."""
    from sklearn.ensemble import HistGradientBoostingClassifier
    from sklearn.linear_model import LogisticRegression
    from sklearn.pipeline import make_pipeline
    from sklearn.preprocessing import StandardScaler

    # The training set is already class-balanced (experiments.train_ml), so no class weights:
    # predicted probabilities then sit around 0.5 at the decision boundary and the shared
    # threshold grid (5..95) spans them.
    logreg = make_pipeline(StandardScaler(), LogisticRegression(max_iter=1000))
    gbt = HistGradientBoostingClassifier(max_iter=200, learning_rate=0.1, max_leaf_nodes=31,
                                         random_state=seed)
    logreg.fit(X, y)
    gbt.fit(X, y)
    return {"logreg": logreg, "gbt": gbt, "prior": float(prior)}


def score(model, ind: np.ndarray, prior: float = 0.5, window: int = 10) -> np.ndarray:
    """Risk score in [0, 100] = 100 * probability of an onset within H_max, corrected from
    the balanced training prior (0.5) back to the true prior: odds_true = odds_model *
    prior / (1 - prior)."""
    if len(ind) == 0:
        return np.zeros(0)
    # float64 + log-odds: probabilities that round to exactly 1.0 in float32 must not
    # produce a 0/0 (NaN), which would silently suppress alarms.
    p = np.clip(model.predict_proba(features(ind, window))[:, 1].astype(np.float64), 1e-12, 1 - 1e-12)
    logit = np.log(p) - np.log1p(-p) + np.log(prior) - np.log1p(-prior)
    return 100.0 / (1.0 + np.exp(-logit))
