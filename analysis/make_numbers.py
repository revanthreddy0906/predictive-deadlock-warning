"""Write every number quoted in the paper's prose as LaTeX macros (paper/numbers.tex),
so the text can never drift from the result files.

    python -m analysis.make_numbers --run results/b_main --tuning results/b_tuning --scaling results/scaling

Naming: \\<Method><Metric>[<Suffix>], e.g. \\CombF (combined F1), \\LookFsub (lookahead
F1 on the lookahead subset), \\WaitFdl (waiting ratio F1, deadlock target).
"""

from __future__ import annotations

import argparse
import json
import os

import pandas as pd

M = {"combined": "Comb", "need_pressure": "Need", "contention": "Cont", "waiting_ratio": "Wait",
     "request_rate": "Rate", "availability": "Avail", "lookahead": "Look", "random": "Rand"}
MET = {"precision": "P", "recall": "R", "f1": "F", "f1_lo": "Flo", "f1_hi": "Fhi",
       "fa_per_1000": "FA", "lead_median": "Lead", "lead_ge_5": "LeadFive"}
SCEN = {"normal": "Normal", "spike": "Spike", "deadlock_prone": "Dlp"}


def fmt(v, nd=2):
    if v is None or (isinstance(v, float) and pd.isna(v)):
        return "--"
    if isinstance(v, str):
        return v.replace("_", r"\_")
    if float(v).is_integer() and abs(v) >= 100:
        return f"{int(v):,}".replace(",", "{,}")
    return f"{v:.{nd}f}"


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--run", default="results/main_test")
    ap.add_argument("--tuning", default="results/tuning")
    ap.add_argument("--scaling", default="results/scaling")
    ap.add_argument("--out", default="paper/numbers.tex")
    args = ap.parse_args(argv)
    ev = os.path.join(args.run, "eval")
    read = lambda n: pd.read_csv(os.path.join(ev, f"{n}.csv"))
    macros: dict[str, str] = {}

    def put(name, v, nd=2):
        macros[name] = fmt(v, nd)

    for suffix, df in (("", read("overall")), ("sub", read("lookahead_subset"))):
        for r in df.itertuples():
            for col, short in MET.items():
                if hasattr(r, col):
                    put(f"{M[r.method]}{short}{suffix}", getattr(r, col), 1 if col == "lead_median" else 2)
    for r in read("per_scenario").itertuples():
        put(f"{M[r.method]}F{SCEN[r.scenario]}", r.f1)
        put(f"{M[r.method]}Lead{SCEN[r.scenario]}", r.lead_median, 1)
    dl = read("deadlock_target")
    for r in dl.itertuples():
        put(f"{M[r.method]}Fdl{'L' if r.H_max == 50 else ''}", r.f1)
        put(f"{M[r.method]}Rdl{'L' if r.H_max == 50 else ''}", r.recall)
    for r in read("hmax_sensitivity").itertuples():
        word = {5: "Five", 10: "Ten", 20: "Twenty", 50: "Fifty"}[r.H_max]
        put(f"{M[r.method]}FH{word}", r.f1)
    for r in read("ablation").itertuples():
        key = r.method.split("[")[1].rstrip("]").replace("drop_", "Drop").replace("_", "")
        put(f"Abl{key.title().replace('Drop', 'Drop')}", r.f1)
    ep = read("episode_outcomes")
    for r in ep.itertuples():
        put(f"EpDead{SCEN[r.scenario]}", 100 * r.deadlocked_frac, 0)
        put(f"EpRec{SCEN[r.scenario]}", 100 * r.recovered_frac, 0)
        put(f"EpN{SCEN[r.scenario]}", r.ep_recovered + r.ep_deadlocked, 0)
    sp = read("spike_timing").iloc[0]
    put("SpikeMedSteps", sp.median_steps_from_spike_start, 0)
    put("SpikeBefore", 100 * sp.event_before_spike, 1)
    for r in read("paired_leads").itertuples():
        put(f"Pair{M[r.method]}N", r.pairs, 0)
        put(f"Pair{M[r.method]}Comb", r.combined_median, 0)
        put(f"Pair{M[r.method]}Other", r.other_median, 0)
        put(f"Pair{M[r.method]}Earlier", 100 * r.combined_earlier_frac, 0)
    setup = read("setup")
    for r in setup.groupby("scenario").agg(with_event=("with_event", "mean")).reset_index().itertuples():
        put(f"WithEvent{SCEN[r.scenario]}", 100 * r.with_event, 0)

    meta = json.load(open(os.path.join(args.run, "meta.json")))
    tmeta = json.load(open(os.path.join(args.tuning, "meta.json")))
    put("NSeqTest", meta["totals"]["sequences"], 0)
    put("NStepsTest", meta["totals"]["steps"], 0)
    put("NSeqTune", tmeta["totals"]["sequences"], 0)
    put("NStepsTune", tmeta["totals"]["steps"], 0)
    put("NSeqAll", meta["totals"]["sequences"] + tmeta["totals"]["sequences"], 0)
    put("NStepsAllM", (meta["totals"]["steps"] + tmeta["totals"]["steps"]) / 1e6, 1)
    put("NSeedsPerCell", meta["config"]["seeds"]["count"], 0)
    put("NSizes", len(meta["config"]["sizes"]), 0)
    put("MaxN", max(s["processes"] for s in meta["config"]["sizes"]), 0)
    put("Machine", meta["machine"].get("instance_type", "local"))
    put("CPUs", meta["machine"]["cpu_count"], 0)
    put("RamGB", meta["machine"]["ram_gb"], 0)
    put("Platform", meta["machine"]["platform"])
    put("GitCommit", (meta.get("git", {}).get("commit") or "")[:7])
    put("NEventsTest", int(read("overall").set_index("method").loc["combined", "events"]), 0)

    best = json.load(open(os.path.join(args.tuning, "best_params.json")))["best"]
    for m, p in best.items():
        if m == "random":
            put("RandP", 1000 * p["p"], 2)  # per 1000 eligible steps
            continue
        put(f"{M[m]}Th", p["threshold"], 0)
        put(f"{M[m]}K", p["k"], 0)
        put(f"{M[m]}Rf", p["R"], 0)
    put("CombW", best["combined"]["weights_name"])

    sc = os.path.join(args.scaling, "scaling.csv")
    if os.path.exists(sc):
        s = pd.read_csv(sc)
        fits = pd.read_csv(os.path.join(args.scaling, "scaling_fits.csv"))
        big = s[s.n == s.n.max()]
        put("SpeedupMax", big.speedup.max(), 1)
        put("SpeedupMin", s[s.n == s.n.min()].speedup.min(), 1)
        put("ScaleMaxN", s.n.max(), 0)
        f = fits.set_index(["metric", "m"]).slope_log_n
        put("SlopeVec", f.loc[("vectorised_us_random_states", 20)])
        put("SlopeRef", f.loc[("reference_us_random_states", 20)])
        put("SafetyUsMax", big.safety_us_per_call.max(), 1)

    lines = ["% Generated by analysis/make_numbers.py. Do not edit by hand."]
    lines += [rf"\newcommand{{\{k}}}{{{v}}}" for k, v in sorted(macros.items())]
    os.makedirs(os.path.dirname(args.out), exist_ok=True)
    open(args.out, "w").write("\n".join(lines) + "\n")
    print(f"{len(macros)} macros -> {args.out}")


if __name__ == "__main__":
    main()
