"""Event-based evaluation (Section 3.5 + PLAN_FIXES A1, A5-A7).

Per sequence, for alarm onsets `alarms` and event onsets `events`:

  valid window of event d     [d - H_max, d - H_min]
  true alarm                  an event (any, including too-early ones) in [a + H_min, a + H_max]
                              (glossary definition: the alarm is followed by an onset
                              within the horizon; several alarms before one event are
                              all true, but only the first captures it)
  censored alarm              not true, sequence stopped at the step cap
                              (end_reason == "max_steps") and a > T - 1 - H_max
  false alarm                 otherwise (also in the tail of sequences that ended in
                              deadlock or all_finished, whose future is known)
  captured event              has an alarm in its window not already used by an earlier
                              event (F7); lead = d - earliest such alarm (F6)
  uncatchable event           d < uncatchable_before (fix A5): excluded from recall for
                              every method, counted separately
Aggregates are micro-averaged (sum counts, then divide; fix A6).
"""

from __future__ import annotations

import numpy as np
import pandas as pd

UNCATCHABLE_BEFORE = 3   # k_max - 1 + H_min, with k_max = 3 and H_min = 1
COUNT_COLS = ("alarms", "true", "false", "censored", "events", "captured", "uncatchable", "T")


def evaluate_sequence(alarms, events, T: int, end_reason: str, H_min: int = 1, H_max: int = 20,
                      uncatchable_before: int = UNCATCHABLE_BEFORE) -> dict:
    alarms = np.asarray(alarms, dtype=np.int64)
    events = np.asarray(events, dtype=np.int64)

    true = false = censored = 0
    for a in alarms:
        j = np.searchsorted(events, a + H_min, side="left")
        if j < events.size and events[j] <= a + H_max:
            true += 1
        elif end_reason == "max_steps" and a > T - 1 - H_max:
            censored += 1
        else:
            false += 1

    catchable = events[events >= uncatchable_before]
    used = np.zeros(alarms.size, bool)
    leads: dict[int, int] = {}
    for d in catchable:
        lo = np.searchsorted(alarms, d - H_max, side="left")
        hi = np.searchsorted(alarms, d - H_min, side="right")
        for i in range(lo, hi):
            if not used[i]:
                used[i] = True
                leads[int(d)] = int(d - alarms[i])
                break

    return {
        "alarms": int(alarms.size), "true": true, "false": false, "censored": censored,
        "events": int(catchable.size), "captured": len(leads),
        "uncatchable": int(events.size - catchable.size), "T": int(T),
        "quiet": bool(alarms.size == 0 and events.size == 0),
        "leads": leads,
    }


def _ratio(num, den):
    return np.divide(num, den, out=np.full(np.shape(num), np.nan, dtype=float),
                     where=np.asarray(den) > 0)


def summarize_counts(true, false, events, captured, T) -> dict:
    """Metrics from (possibly arrays of) summed counts."""
    precision = _ratio(np.asarray(true, float), np.asarray(true, float) + false)
    recall = _ratio(np.asarray(captured, float), np.asarray(events, float))
    pr = np.nan_to_num(precision) + np.nan_to_num(recall)
    f1 = _ratio(2 * np.nan_to_num(precision) * np.nan_to_num(recall), pr)
    f1 = np.where(pr > 0, f1, 0.0)
    fa = _ratio(1000.0 * np.asarray(false, float), np.asarray(T, float))
    return {"precision": precision, "recall": recall, "f1": f1, "fa_per_1000": fa}


def lead_stats(leads: list[int] | np.ndarray) -> dict:
    x = np.asarray(leads, dtype=float)
    if x.size == 0:
        return {"lead_mean": np.nan, "lead_median": np.nan, "lead_q1": np.nan, "lead_q3": np.nan,
                **{f"lead_ge_{k}": np.nan for k in (1, 3, 5, 10)}}
    out = {"lead_mean": x.mean(), "lead_median": float(np.median(x)),
           "lead_q1": float(np.percentile(x, 25)), "lead_q3": float(np.percentile(x, 75))}
    for k in (1, 3, 5, 10):
        out[f"lead_ge_{k}"] = float((x >= k).mean())
    return out


def aggregate(rows: list[dict] | pd.DataFrame) -> dict:
    """Micro-averaged metrics over per-sequence results from evaluate_sequence."""
    df = pd.DataFrame(rows) if not isinstance(rows, pd.DataFrame) else rows
    s = df[list(COUNT_COLS)].sum()
    out = {k: int(s[k]) for k in COUNT_COLS}
    out.update({k: float(v) for k, v in
                summarize_counts(s["true"], s["false"], s["events"], s["captured"], s["T"]).items()})
    out["quiet_sequences"] = int(df["quiet"].sum()) if "quiet" in df else 0
    out["sequences"] = int(len(df))
    leads = [v for d in df["leads"] for v in d.values()] if "leads" in df else []
    out.update(lead_stats(leads))
    return out


def bootstrap_ci(df: pd.DataFrame, strata=("scenario", "n"), B: int = 1000, seed: int = 0,
                 alpha: float = 0.05) -> dict:
    """Percentile CIs for precision/recall/F1/FA rate, resampling sequences within each
    stratum (fix A7)."""
    rng = np.random.default_rng(seed)
    cols = ["true", "false", "events", "captured", "T"]
    totals = np.zeros((B, len(cols)))
    for _, g in df.groupby(list(strata), sort=False, observed=True):
        x = g[cols].to_numpy(dtype=float)
        idx = rng.integers(0, len(x), size=(B, len(x)))
        totals += x[idx].sum(axis=1)
    m = summarize_counts(*totals.T)
    out = {}
    for k, v in m.items():
        v = v[~np.isnan(v)]
        out[k] = (float(np.percentile(v, 100 * alpha / 2)), float(np.percentile(v, 100 * (1 - alpha / 2)))) \
            if v.size else (np.nan, np.nan)
    return out


def paired_leads(leads_a: list[dict], leads_b: list[dict]) -> tuple[np.ndarray, np.ndarray]:
    """Lead times of two methods on events both captured (F11). Inputs are per-sequence
    {event_step: lead} dicts aligned by sequence."""
    a, b = [], []
    for da, db in zip(leads_a, leads_b):
        for d in da.keys() & db.keys():
            a.append(da[d])
            b.append(db[d])
    return np.array(a), np.array(b)
