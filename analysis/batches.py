"""Post-hoc analyses on the stored per-sequence evaluation rows (no new simulation).

E8: deadlock-onset target recomputed on the common subset where exact lookahead was computed.
E1: independent seed batches as the experimental unit. Within every (scenario, n) cell the test
    seeds are dealt round-robin into B batches, so each batch is a stratified replicate of the
    whole test split; F1 is pooled within a batch and methods are compared by paired per-batch
    differences (mean, t interval over batches).
E2: two one-sided tests (TOST) on the paired batch-level F1 difference safety margin - exact
    lookahead on the common subset, against an equivalence margin delta.

Thresholds are the ones tuned once on the tuning split, so batches replicate the test-side
sampling only, not tuning.

    python -m analysis.batches --run results_ec2_c/results/c_main --batches 20 --delta 0.05
"""
from __future__ import annotations

import argparse
import json
import os

import numpy as np
import pandas as pd
from scipy import stats

from experiments.evaluate import table
from pdw import metrics

COLS = ["scenario", "n", "m", "seed", "has_lookahead", "method", "target", "H_max",
        "alarms", "true", "false", "censored", "events", "captured", "uncatchable", "T", "leads"]
SUMS = ["true", "false", "events", "captured", "T"]


def assign_batches(rows: pd.DataFrame, B: int) -> pd.Series:
    """Round-robin seeds into B batches within each (scenario, n) cell."""
    seqs = rows[["scenario", "n", "seed"]].drop_duplicates().sort_values(["scenario", "n", "seed"])
    seqs["batch"] = seqs.groupby(["scenario", "n"], observed=True).cumcount() % B
    return rows.merge(seqs, on=["scenario", "n", "seed"], how="left")["batch"].to_numpy()


def batch_f1(rows: pd.DataFrame) -> pd.DataFrame:
    """F1 per (batch, method), pooled over the sequences of the batch."""
    s = rows.groupby(["batch", "method"], observed=True)[SUMS].sum().reset_index()
    s["f1"] = metrics.summarize_counts(s["true"], s["false"], s["events"], s["captured"], s["T"])["f1"]
    return s.pivot(index="batch", columns="method", values="f1")


def paired(f1: pd.DataFrame, a: str, b: str, level: float = 0.95) -> dict:
    d = (f1[a] - f1[b]).dropna().to_numpy()
    k = d.size
    se = d.std(ddof=1) / np.sqrt(k)
    t = stats.t.ppf(0.5 + level / 2, k - 1)
    return {"a": a, "b": b, "batches": k, "mean_a": float(f1[a].mean()), "mean_b": float(f1[b].mean()),
            "diff": float(d.mean()), "sd": float(d.std(ddof=1)), "lo": float(d.mean() - t * se),
            "hi": float(d.mean() + t * se), "a_wins": int((d > 0).sum()),
            "p_two_sided": float(stats.ttest_1samp(d, 0.0).pvalue)}


def tost(f1: pd.DataFrame, a: str, b: str, delta: float, alpha: float = 0.05) -> dict:
    """Paired TOST: equivalent if the (1 - 2 alpha) interval of the mean difference lies in (-delta, delta)."""
    d = (f1[a] - f1[b]).dropna().to_numpy()
    k = d.size
    se = d.std(ddof=1) / np.sqrt(k)
    p_lower = 1 - stats.t.cdf((d.mean() + delta) / se, k - 1)  # H0: diff <= -delta
    p_upper = stats.t.cdf((d.mean() - delta) / se, k - 1)      # H0: diff >= +delta
    t = stats.t.ppf(1 - alpha, k - 1)
    lo, hi = d.mean() - t * se, d.mean() + t * se
    return {"a": a, "b": b, "batches": k, "delta": delta, "diff": float(d.mean()),
            "ci90_lo": float(lo), "ci90_hi": float(hi), "p_lower": float(p_lower), "p_upper": float(p_upper),
            "p_tost": float(max(p_lower, p_upper)), "equivalent": bool(max(p_lower, p_upper) < alpha),
            "smallest_delta_equivalent": float(max(abs(lo), abs(hi)))}


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--run", default="results_ec2_c/results/c_main")
    ap.add_argument("--batches", type=int, default=20)
    ap.add_argument("--delta", type=float, default=0.05)
    ap.add_argument("--bootstrap", type=int, default=1000)
    args = ap.parse_args(argv)
    ev = os.path.join(args.run, "eval")
    out = os.path.join(ev, "batches")
    os.makedirs(out, exist_ok=True)

    rows = pd.read_parquet(os.path.join(ev, "rows.parquet"), columns=COLS,
                           filters=[("target", "in", ["unsafe", "deadlock"]), ("H_max", "in", [20, 50])])
    rows = rows[rows.target.isin(["unsafe", "deadlock"])]
    for c in ("scenario", "method", "target"):
        rows[c] = rows[c].astype(str)

    # E8: deadlock target on the common subset, all methods on identical sequences
    dl = rows[(rows.target == "deadlock") & rows.has_lookahead]
    e8 = table(dl, ["H_max", "method"], ci=True, B=args.bootstrap)
    e8.to_csv(os.path.join(out, "deadlock_common_subset.csv"), index=False)

    main_rows = rows[(rows.target == "unsafe") & (rows.H_max == 20)].copy()
    main_rows["batch"] = assign_batches(main_rows, args.batches)
    sub = main_rows[main_rows.has_lookahead]

    f1_full, f1_sub = batch_f1(main_rows), batch_f1(sub)
    f1_full.to_csv(os.path.join(out, f"batch_f1_full_B{args.batches}.csv"))
    f1_sub.to_csv(os.path.join(out, f"batch_f1_subset_B{args.batches}.csv"))

    # E1: paired comparisons with the batch as the unit
    pairs = [(f1_full, "full", "combined", m) for m in
             ("random", "availability", "contention", "logreg", "gbt", "margin", "approx_lookahead")]
    pairs += [(f1_sub, "subset", "margin", "lookahead"), (f1_sub, "subset", "approx_lookahead", "lookahead"),
              (f1_sub, "subset", "gbt", "lookahead"), (f1_sub, "subset", "combined", "lookahead")]
    e1 = pd.DataFrame([{"population": p, **paired(f, a, b)} for f, p, a, b in pairs])
    e1.to_csv(os.path.join(out, f"paired_B{args.batches}.csv"), index=False)

    # spread of batch-level F1 per method, for comparison with the sequence bootstrap intervals
    spread = pd.DataFrame({"population": "full", "method": f1_full.columns, "mean": f1_full.mean().values,
                           "sd": f1_full.std(ddof=1).values, "min": f1_full.min().values,
                           "max": f1_full.max().values})
    spread_s = pd.DataFrame({"population": "subset", "method": f1_sub.columns, "mean": f1_sub.mean().values,
                             "sd": f1_sub.std(ddof=1).values, "min": f1_sub.min().values,
                             "max": f1_sub.max().values})
    pd.concat([spread, spread_s]).to_csv(os.path.join(out, f"spread_B{args.batches}.csv"), index=False)

    # E2: TOST for H2
    e2 = pd.DataFrame([tost(f1_sub, "margin", "lookahead", args.delta),
                       tost(f1_sub, "approx_lookahead", "lookahead", args.delta)])
    e2.to_csv(os.path.join(out, f"tost_B{args.batches}.csv"), index=False)

    with open(os.path.join(out, f"meta_B{args.batches}.json"), "w") as fh:
        json.dump({"batches": args.batches, "delta": args.delta, "bootstrap": args.bootstrap,
                   "sequences_full": int(main_rows[["scenario", "n", "seed"]].drop_duplicates().shape[0]),
                   "sequences_subset": int(sub[["scenario", "n", "seed"]].drop_duplicates().shape[0])}, fh, indent=1)

    pd.set_option("display.width", 200)
    print(e8[["H_max", "method", "precision", "recall", "f1", "f1_lo", "f1_hi", "events"]].round(3).to_string())
    print(e1.round(4).to_string())
    print(e2.round(4).to_string())


if __name__ == "__main__":
    main()
