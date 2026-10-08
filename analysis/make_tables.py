"""Phase 14 tables (LaTeX into paper/tables/), all generated from result files.

    python -m analysis.make_tables --run results/main_test --tuning results/tuning --scaling results/scaling
"""

from __future__ import annotations

import argparse
import json
import os

import numpy as np
import pandas as pd

ORDER = ["combined", "need_pressure", "contention", "waiting_ratio", "request_rate", "availability", "lookahead", "random"]


def fmt(x, nd=2):
    if isinstance(x, (int, np.integer)):
        return f"{int(x):,}".replace(",", "{,}")
    if isinstance(x, str):
        return x.replace("%", r"\%").replace("_", r"\_")
    if pd.isna(x):
        return "--"
    if isinstance(x, (int,)) or (isinstance(x, float) and x.is_integer() and abs(x) >= 10):
        return f"{int(x):,}".replace(",", "{,}")
    return f"{x:.{nd}f}"


def latex(df: pd.DataFrame, caption: str, label: str, nd=2, wide=False, place="t") -> str:
    cols = list(df.columns)
    env = "table*" if wide else "table"
    lines = [rf"\begin{{{env}}}[{place}]", r"\centering", r"\footnotesize", rf"\caption{{{caption}}}", rf"\label{{{label}}}",
             r"\begin{tabular}{" + "l" + "r" * (len(cols) - 1) + "}", r"\toprule",
             " & ".join(fmt(c) for c in cols) + r" \\", r"\midrule"]
    for row in df.astype(object).itertuples(index=False):  # iterrows would upcast ints to floats
        lines.append(" & ".join(fmt(v, nd) for v in row) + r" \\")
    lines += [r"\bottomrule", r"\end{tabular}", rf"\end{{{env}}}", ""]
    return "\n".join(lines)


def ci(df, k):
    return df.apply(lambda r: f"{r[k]:.2f} [{r[k + '_lo']:.2f}, {r[k + '_hi']:.2f}]" if pd.notna(r[k]) else "--", axis=1)


def ordered(df):
    df = df.copy()
    df["_o"] = df["method"].map({m: i for i, m in enumerate(ORDER)}).fillna(99)
    return df.sort_values("_o").drop(columns="_o")


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--run", default="results/main_test")
    ap.add_argument("--tuning", default="results/tuning")
    ap.add_argument("--scaling", default="results/scaling")
    ap.add_argument("--out", default="paper/tables")
    args = ap.parse_args(argv)
    os.makedirs(args.out, exist_ok=True)
    ev = os.path.join(args.run, "eval")
    read = lambda name: pd.read_csv(os.path.join(ev, f"{name}.csv"))
    write = lambda name, s: open(os.path.join(args.out, f"{name}.tex"), "w").write(s)

    meta = json.load(open(os.path.join(args.run, "meta.json")))
    tmeta = json.load(open(os.path.join(args.tuning, "meta.json")))
    setup = read("setup")
    order = {"normal": 0, "spike": 1, "deadlock_prone": 2}
    s = setup.assign(_o=setup.scenario.map(order)).sort_values(["_o", "n"]).drop(columns="_o")
    s["with_event"] = (100 * s["with_event"]).round(1)
    s["deadlock_end"] = (100 * s["deadlock_end"]).round(1)
    s = s[["scenario", "n", "m", "sequences", "steps", "events", "with_event", "deadlock_end", "tightness"]]
    s.columns = ["scenario", "n", "m", "seqs", "steps", "events", "% with event", "% deadlock", "tightness"]
    tot = (f"Test split: {meta['totals']['sequences']:,} sequences, {meta['totals']['steps']:,} steps; "
           f"tuning split: {tmeta['totals']['sequences']:,} sequences, {tmeta['totals']['steps']:,} steps. "
           f"Machine: {meta['machine']['platform']} ({meta['machine']['cpu_count']} CPUs, "
           f"{meta['machine'].get('instance_type', 'local')}).")
    write("tab_setup", latex(s, "Experimental setup per cell (test split). " + tot.replace("_", r"\_"), "tab:setup", 2, wide=True))

    o = ordered(read("overall"))
    t = pd.DataFrame({"method": o.method, "precision": ci(o, "precision"), "recall": ci(o, "recall"),
                      "F1": ci(o, "f1"), "FA/1000": o.fa_per_1000, "lead med.": o.lead_median.map(lambda v: f"{v:.0f}" if pd.notna(v) else "--"),
                      r"lead$\geq$5": o.lead_ge_5, "alarms": o.alarms.round().astype(int)})
    write("tab_main", latex(t, "Main results, unsafe target, $H_{max}=20$, test split, 95\\% bootstrap CIs.", "tab:main", wide=True))

    p = read("per_scenario")
    p = ordered(p)
    t = p.pivot_table(index="method", columns="scenario", values="f1", sort=False).reindex(
        [m for m in ORDER if m in p.method.unique()]).reset_index()
    write("tab_per_scenario", latex(t, "F1 per scenario (unsafe target, $H_{max}=20$).", "tab:scenario"))

    d = read("deadlock_target")
    d = ordered(d[d.H_max == 20])
    t = pd.DataFrame({"method": d.method, "precision": d.precision, "recall": d.recall, "F1": d.f1,
                      "lead med.": d.lead_median.map(lambda v: f"{v:.0f}" if pd.notna(v) else "--"), "events": d.events})
    write("tab_deadlock", latex(t, "Deadlock-onset target ($H_{max}=20$, alarms not masked while unsafe).", "tab:deadlock"))

    a = read("ablation")
    t = a[["method", "precision", "recall", "f1", "fa_per_1000"]].copy()
    t["method"] = t["method"].str.replace("combined[equal]", "all five, equal", regex=False) \
        .str.replace(r"combined\[drop_(.*)\]", r"without \1", regex=True)
    t.columns = ["variant", "precision", "recall", "F1", "FA/1000"]
    write("tab_ablation", latex(t, "Ablation: combined score with one indicator removed (each re-tuned on the tuning split).", "tab:ablation"))

    l = ordered(read("lookahead_subset"))
    t = pd.DataFrame({"method": l.method, "precision": l.precision, "recall": l.recall, "F1": ci(l, "f1"),
                      "lead med.": l.lead_median.map(lambda v: f"{v:.0f}" if pd.notna(v) else "--")})
    write("tab_lookahead", latex(t, "All methods on the sequences where the lookahead baseline was computed.", "tab:lookahead"))

    e = read("episode_outcomes")
    write("tab_episodes", latex(e, "Unsafe-episode outcomes per scenario.", "tab:episodes", wide=True))

    pl = read("paired_leads")
    write("tab_paired", latex(pl, "Paired lead times: combined vs each method, on events both captured.", "tab:paired", wide=True))

    sc = os.path.join(args.scaling, "scaling.csv")
    if os.path.exists(sc):
        df = pd.read_csv(sc)[["n", "m", "vectorised_us_random_states", "reference_us_random_states", "speedup",
                              "us_per_step"]]
        df.columns = ["n", "m", "vec µs", "ref µs", "speed-up", "µs/step"]
        write("tab_scaling", latex(df, "Runtime scaling: time per Banker's safety check on random valid states "
                                       "(vectorised vs. reference) and whole-simulator time per step.",
                                   "tab:scaling", nd=1, place="!htb").replace("µ", r"$\mu$"))
    print("tables written to", args.out)


if __name__ == "__main__":
    main()
