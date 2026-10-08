"""Generate the plain-language project report (paper/REPORT.md) from the result files.

    python -m analysis.make_report --run results/b_main --tuning results/b_tuning \
        --scaling results/scaling --aws deployment/aws_run.json
"""

from __future__ import annotations

import argparse
import json
import os

import pandas as pd

ORDER = ["combined", "contention", "need_pressure", "waiting_ratio", "request_rate", "availability", "lookahead", "random"]
NICE = {"combined": "Combined score (ours)", "need_pressure": "Need pressure", "contention": "Contention",
        "waiting_ratio": "Waiting ratio", "request_rate": "Request rate", "availability": "Availability (free-resource rule)",
        "lookahead": "Lookahead (exact, expensive)", "random": "Random alarms (chance)"}


def f2(x):
    return "–" if pd.isna(x) else f"{x:.2f}"


def table(df: pd.DataFrame) -> str:
    cols = list(df.columns)
    out = ["| " + " | ".join(cols) + " |", "|" + "|".join("---" for _ in cols) + "|"]
    for _, r in df.iterrows():
        out.append("| " + " | ".join(str(v) for v in r.values) + " |")
    return "\n".join(out)


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--run", default="results/main_test")
    ap.add_argument("--tuning", default="results/tuning")
    ap.add_argument("--scaling", default="results/scaling")
    ap.add_argument("--aws", default="deployment/aws_run.json")
    ap.add_argument("--out", default="paper/REPORT.md")
    args = ap.parse_args(argv)
    ev = os.path.join(args.run, "eval")
    read = lambda n: pd.read_csv(os.path.join(ev, f"{n}.csv"))
    meta = json.load(open(os.path.join(args.run, "meta.json")))
    tmeta = json.load(open(os.path.join(args.tuning, "meta.json")))
    best = json.load(open(os.path.join(args.tuning, "best_params.json")))["best"]
    aws = json.load(open(args.aws)) if os.path.exists(args.aws) else None

    ov = read("overall").set_index("method")
    sub = read("lookahead_subset").set_index("method")
    ps = read("per_scenario")
    dl = read("deadlock_target")
    ep = read("episode_outcomes").set_index("scenario")
    abl = read("ablation")
    pairs = read("paired_leads").set_index("method")
    spike = read("spike_timing").iloc[0]
    setup = read("setup")
    hs = read("hmax_sensitivity")
    c = ov.loc["combined"]

    n_seq = meta["totals"]["sequences"] + tmeta["totals"]["sequences"]
    n_steps = meta["totals"]["steps"] + tmeta["totals"]["steps"]
    machine = meta["machine"]
    where = (f"AWS EC2 **{machine['instance_type']}** ({machine['cpu_count']} vCPUs, {machine['ram_gb']} GB RAM, "
             f"region ap-south-2 / Hyderabad)" if machine.get("instance_type", "local") != "local"
             else f"the MacBook ({machine['cpu_count']} cores) — dry run")

    main_rows = []
    for m in ORDER:
        if m not in ov.index:
            continue
        r = ov.loc[m]
        main_rows.append({"Method": NICE[m], "Precision": f2(r.precision), "Recall": f2(r.recall),
                          "F1 [95% CI]": f"{f2(r.f1)} [{f2(r.f1_lo)}–{f2(r.f1_hi)}]",
                          "False alarms / 1000 steps": f2(r.fa_per_1000),
                          "Median lead (steps)": "–" if pd.isna(r.lead_median) else f"{r.lead_median:.0f}"})
    scen_rows = []
    for m in ORDER:
        g = ps[ps.method == m].set_index("scenario")
        if g.empty:
            continue
        scen_rows.append({"Method": NICE[m], **{s: f2(g.loc[s, "f1"]) if s in g.index else "–"
                                               for s in ("normal", "spike", "deadlock_prone")}})
    dl20 = dl[dl.H_max == 20].set_index("method")
    dl50 = dl[dl.H_max == 50].set_index("method")
    dl_rows = [{"Method": NICE[m], "F1 (H=20)": f2(dl20.loc[m, "f1"]), "F1 (H=50)": f2(dl50.loc[m, "f1"])}
               for m in ORDER if m in dl20.index]
    abl_rows = [{"Variant": r.method.replace("combined[equal]", "all five indicators, equal weights")
                 .replace("combined[drop_", "without ").rstrip("]").replace("_", " "), "F1": f2(r.f1)}
                for r in abl.itertuples()]
    setup_rows = setup.assign(with_event=(100 * setup.with_event).round(0).astype(int).astype(str) + "%",
                              deadlock_end=(100 * setup.deadlock_end).round(0).astype(int).astype(str) + "%",
                              tightness=setup.tightness.round(2))[
        ["scenario", "n", "m", "sequences", "steps", "with_event", "deadlock_end", "tightness"]]
    setup_rows.columns = ["Scenario", "Processes", "Resource types", "Sequences", "Steps",
                          "With ≥1 unsafe event", "Ended in deadlock", "Claim tightness"]
    h = hs[hs.method == "combined"].set_index("H_max").f1

    sc_text = ""
    sc_path = os.path.join(args.scaling, "scaling.csv")
    if os.path.exists(sc_path):
        sc = pd.read_csv(sc_path)
        fits = pd.read_csv(os.path.join(args.scaling, "scaling_fits.csv")).set_index(["metric", "m"]).slope_log_n
        sc_text = (f"The NumPy (vectorised) Banker's check was **{sc[sc.n == sc.n.min()].speedup.min():.1f}× to "
                   f"{sc[sc.n == sc.n.max()].speedup.max():.1f}× faster** than the plain textbook loop "
                   f"(from {sc.n.min()} to {sc.n.max()} processes). Theory says the check costs Θ(m·n²) in the worst "
                   f"case, but the measured growth was much gentler (log–log slope ≈ "
                   f"{fits.loc[('vectorised_us_random_states', 20)]:.2f} vectorised and "
                   f"{fits.loc[('reference_us_random_states', 20)]:.2f} for the textbook loop at m = 20): real states "
                   f"usually clear in a few passes, so the worst case almost never happens.")

    aws_text = "The cloud run log is not available."
    if aws:
        aws_text = "\n".join(f"- **{k}:** {v}" for k, v in aws.items())

    look_cost, look_n = float("nan"), None
    summ = os.path.join(args.run, "summary.parquet")
    if os.path.exists(summ):
        sm = pd.read_parquet(summ)
        lkr = sm[sm.lookahead_time > 0]
        look_n = int(lkr.n.max())
        big = lkr[lkr.n == look_n]
        look_cost = big.lookahead_time.sum() / (big.runtime - big.lookahead_time).sum()
    lk = sub.loc["lookahead"]
    cs = sub.loc["combined"]
    pl = pairs.loc["lookahead"]
    pa = pairs.loc["availability"]

    md = f"""---
title: "Predictive Deadlock Warning — Project Report"
subtitle: "Operating Systems case study, CBIT (Information Technology)"
author: "Revanth Reddy Lingala and Sujju"
date: "October 2026"
---

# 1. Summary in one page

**Question.** Banker's algorithm tells an operating system whether the current state is *safe right now*. It does
not warn that the system is *heading towards* danger. We asked: **can simple, explainable signals raise an alarm a
few steps before Banker's algorithm reports an unsafe state — how early, and how reliably?**

**What we built.** A resource-allocation simulator (with Banker's safety check and deadlock detection), three
workload scenarios, a rule-based early-warning algorithm (no machine learning), an evaluation method borrowed from
hospital and earthquake early-warning systems, and an experiment pipeline. Everything is tested by 122 automated
tests.

**How big the experiment was.** {n_seq:,} simulated sequences — {n_steps / 1e6:.0f} million resource requests,
each followed by a Banker's safety check — across 3 scenarios and {len(meta['config']['sizes'])} system sizes
(10 to {max(s['processes'] for s in meta['config']['sizes'])} processes), run on {where}.
Settings were tuned on {tmeta['totals']['sequences']:,} sequences and all reported numbers come from a separate
{meta['totals']['sequences']:,} sequences the tuner never saw.

**Main answers.**

1. **Yes, early warning works — moderately.** Our combined score catches {100 * c.recall:.0f}% of unsafe onsets
   in advance with {100 * c.precision:.0f}% of its alarms correct (F1 = {f2(c.f1)}), giving a median
   **{c.lead_median:.0f} steps of warning**. Random alarms at the same rate score F1 = {f2(ov.loc['random', 'f1'])},
   and the simple "free resources are low" rule scores {f2(ov.loc['availability', 'f1'])}.
2. **Contention is the single most useful signal** (F1 = {f2(ov.loc['contention', 'f1'])} on its own). Averaging in
   weaker signals dilutes it: the tuner's best combination doubled contention's weight
   ("{best['combined']['weights_name']}").
3. **An exact one-step lookahead check is much more accurate** (F1 = {f2(lk.f1)} vs {f2(cs.f1)} for our score on
   the same sequences), with **similar lead times** on the events both caught (median {pl.other_median:.0f} steps for lookahead,
   {pl.combined_median:.0f} for ours), **but it is expensive**: one extra safety check per running process per step,
   {look_cost:.0f}× the computation of the whole simulation at {look_n} processes. Cheap-and-moderate versus
   exact-and-costly is the central trade-off.
4. **Sudden bursts are easiest to predict, slow build-ups hardest** (F1 {f2(ps[(ps.method == 'combined') & (ps.scenario == 'spike')].f1.iloc[0])}
   for spikes vs {f2(ps[(ps.method == 'combined') & (ps.scenario == 'normal')].f1.iloc[0])} for normal workloads).
5. **"Unsafe" almost always became "deadlock"** in our model ({ep.loc['spike', 'deadlocked_frac'] * 100:.0f}% of
   unsafe episodes for spikes, {ep.loc['normal', 'deadlocked_frac'] * 100:.0f}% for normal workloads), because
   processes really do end up requesting their full declared claims.

# 2. Background: the ideas in plain words

- **Process:** a running program that holds and requests resources.
- **Resource type:** a kind of resource (memory blocks, a printer, a file lock) with a fixed number of units.
- **Maximum claim:** the most units of each type a process says it may ever need. **Need** = claim − what it holds.
- **Safe state:** Banker's algorithm can find *some order* in which every process could get its full need and finish.
- **Unsafe state:** no such order exists. This is *danger*, not yet necessarily a deadlock.
- **Deadlock:** some waiting processes can never be satisfied even if everyone else finishes. A deadlocked state is
  always unsafe; a safe state is never deadlocked (our tests check this on thousands of random states).

Banker's algorithm is like a fire alarm: it rings when the fire is already there. We are testing a smoke detector.

# 3. What we built

![Example test runs, one per scenario: the risk score (blue) rises, an alarm fires (triangle), then the system turns unsafe (red band) and deadlocks (red line).](figures/fig1_timelines.png){{ width=100% }}

## 3.1 The simulator ("observer mode")
In a real system, Banker's algorithm *refuses* dangerous requests, so the system never becomes unsafe — and there
would be nothing to predict. Our simulator therefore **grants every valid request** and uses Banker's algorithm
only to *watch*. Every step:

1. Waiting processes are retried, longest-waiting first; a process whose claim is now fully met finishes and returns
   everything, and the retry repeats with the freed units.
2. One process makes a new request (never zero, never more than its remaining need). If the units are free it is
   granted — **even if this makes the state unsafe** — otherwise the process waits.
3. Finished processes release their resources; in the *normal* scenario a process may also give some back early.
4. We record: is the state unsafe (Banker's)? is it deadlocked (detection)? and the five warning signals.

A run ends at the first deadlock, when every process has finished, or at a step limit.

## 3.2 Three workloads
| Scenario | What happens | What it tests |
|---|---|---|
| normal | small requests, frequent completions, occasional early releases | false alarms; slow build-up |
| spike | normal traffic, then 80% of processes suddenly grab large chunks and hold them | sudden change |
| deadlock_prone | process *i* keeps asking for resource *i+1* (a circular pattern) and rarely finishes | gradual build-up |

The key setting is **claim tightness** (total declared claims ÷ total units). We calibrated it on practice seeds so
each scenario gives a mix of runs that do and do not become unsafe (Section 6.1).

## 3.3 The warning algorithm
After every step we compute five numbers between 0 and 1:

| Signal | Meaning |
|---|---|
| Scarcity | how much of all resources is already handed out |
| Need pressure | how much is still wanted compared with what is free |
| Contention | for how many resource types two or more processes want more than is free |
| Waiting ratio | what fraction of processes are blocked |
| Request rate | whether requests are speeding up compared with the previous 10 steps |

They are combined into a **risk score from 0 to 100**. An alarm fires when the score stays above a threshold for
*k* steps in a row, and then stays quiet for *R* steps so that one long risky stretch counts once. The tuned setting
was threshold **{best['combined']['threshold']}**, k = {best['combined']['k']}, R = {best['combined']['R']}, using
weights "{best['combined']['weights_name']}".

# 4. Every edge case we handle
Each item below has an automated test (122 tests in total).

- **States:** safe-and-deadlocked never happens; unsafe-but-not-deadlocked is recorded separately; a starting state
  that is unsafe is redrawn; all-finished counts as safe and ends the run; units are never created or lost; a finished
  process never holds anything; the fast Banker's check always agrees with the textbook version.
- **Requests:** never zero; never above the remaining need (flagged and skipped if it ever were); above the free
  units → wait; a request that makes the state unsafe is still granted (observer mode); waiting or finished processes
  never request; waiting processes are retried first-come first-served; no possible requester ends the run.
- **Life-cycle:** a process whose need reaches zero finishes and releases everything; unsafe can recover to safe, so
  one run can have several danger episodes; the same seed always gives the same run; a process finishing during the
  retry frees units for the next waiter in the same step (a bug we found and fixed).
- **Signals:** all zero when nothing is active; no division by zero when nothing is free; request rate is zero until
  there is enough history; every signal always stays within 0–1.
- **Alarms:** a score hovering at the threshold needs *k* steps in a row; a long high stretch fires once per quiet
  period; no alarms while the system is already unsafe.
- **Scoring:** an alarm 1–20 steps before danger is a true alarm; an alarm at the same step is a *miss*
  (detection, not prediction); several alarms before one event — the earliest gives the lead time; one alarm cannot
  claim two events; alarms near the end of a run cut off by the step limit are not counted (the future is unknown),
  but near the end of a run that ended in deadlock they count as false (the future is known); danger that flickers
  unsafe→safe→unsafe within 5 steps is one episode; danger in the first 3 steps is excluded for every method.
- **Experiments:** practice (tuning) seeds and test seeds can never mix (checked in code); a crashed run resumes;
  re-running the same configuration is skipped.

# 5. How the experiments were run

1. **Dry run on the MacBook** (48,000 sequences) to check the whole pipeline and measure timings.
2. **Official run on AWS EC2**, the same code and the same command (`run_all.sh`), at larger scale:
{aws_text}

The pipeline: tests → smoke run → calibration → {tmeta['totals']['sequences']:,} practice runs →
{meta['totals']['sequences']:,} test runs → tuning (≈2,000 settings tried per method) → evaluation with 95%
confidence intervals → speed study → tables and figures. Every run stores its configuration, code version
(commit `{(meta.get('git', {}).get('commit') or '')[:7]}`) and machine details.

# 6. Results

## 6.1 Setup per cell (test split)
{table(setup_rows)}

## 6.2 Main result — can we warn before "unsafe"? (warning window: 20 steps)
{table(pd.DataFrame(main_rows))}

![Precision–recall trade-off for every method (large dots: tuned settings; star: random).](figures/fig3_pr_curves.png){{ width=80% }}

![Lead times of the danger events each method caught.](figures/fig2_lead_times.png){{ width=85% }}

*Precision* = share of alarms that were followed by danger within 20 steps. *Recall* = share of dangers that were
warned about in advance. *F1* combines both. Lookahead is computed on part of the runs (all runs up to 25 processes,
a sample above), so on exactly those runs: lookahead F1 = {f2(lk.f1)}, combined = {f2(cs.f1)}.

**Reading it:** our score is far better than chance and clearly better than the simple free-resource rule. On
danger events that both caught, it warned earlier than the free-resource rule ({pa.combined_median:.0f} vs
{pa.other_median:.0f} steps median); against lookahead the lead times were similar ({pl.combined_median:.0f} vs
{pl.other_median:.0f} steps over {int(pl.pairs):,} shared events).

## 6.3 Which signals matter (ablation)
{table(pd.DataFrame(abl_rows))}

Removing contention or request rate hurts the equal-weight combination most; removing waiting ratio *helps*.
Adding weak signals to a strong one dilutes it, which is why the tuner's best combination doubled contention's
weight.

## 6.4 By scenario (F1)
{table(pd.DataFrame(scen_rows))}

![F1 per scenario with 95% confidence intervals.](figures/fig4_per_scenario_f1.png){{ width=100% }}

Spikes are easiest: several signals rise together, and the danger starts a median {spike.median_steps_from_spike_start:.0f}
steps after the burst begins (only {spike.event_before_spike * 100:.1f}% before it). Slow build-ups give little warning
before the line is crossed; there, waiting ratio alone does better than the combination. Contention's overall lead
comes mainly from spikes.

## 6.5 Unsafe versus deadlock
{table(ep.reset_index()[["scenario", "ep_recovered", "ep_deadlocked", "deadlocked_frac"]].assign(deadlocked_frac=lambda d: (100 * d.deadlocked_frac).round(0).astype(int).astype(str) + "%").rename(columns={"scenario": "Scenario", "ep_recovered": "Recovered", "ep_deadlocked": "Became deadlock", "deadlocked_frac": "Deadlock share"}))}

Predicting the deadlock itself (alarms allowed while already unsafe):

{table(pd.DataFrame(dl_rows))}

![What happened to unsafe episodes in each scenario.](figures/fig6_episode_outcomes.png){{ width=70% }}

With a 20-step window, waiting ratio is the best deadlock predictor (F1 {f2(dl20.loc['waiting_ratio', 'f1'])}):
blocked processes pile up as a deadlock forms. With a 50-step window lookahead leads
({f2(dl50.loc['lookahead', 'f1'])}, on its subset of runs).

## 6.6 Warning window
With the same alarms, a wider window counts more alarms as correct: combined F1 = {f2(h.get(5))} (5 steps),
{f2(h.get(10))} (10), {f2(h.get(20))} (20), {f2(h.get(50))} (50).

## 6.7 Speed
{sc_text}

![Time per Banker's safety check as the number of processes grows (log–log).](figures/fig7_scaling.png){{ width=100% }}

Figures for all of these are in `paper/figures/` (timelines, lead times, precision–recall curves, per-scenario F1,
window sensitivity, episode outcomes, scaling, speed-up).

# 7. Limitations (honest)
- Workloads are synthetic, and processes must declare maximum claims (as Banker's algorithm requires); real systems
  rarely know them.
- The set of processes is fixed (no new arrivals); a run stops at the first deadlock.
- Claim tightness, which largely decides whether a run becomes unsafe, was chosen to give a balanced mix.
- Signals and Banker's check read the same state, so some correlation is built in — this is why we compare against
  random, free-resource and lookahead baselines.
- Lookahead was computed on a subset of runs for large systems.
- Three single-signal baselines (need pressure, request rate, availability) chose the highest threshold in the
  tuning grid, so slightly better settings may exist for them.

# 8. How to reproduce
```
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
.venv/bin/python -m pytest
TUNING_CFG=configs/b_tuning.yaml MAIN_CFG=configs/b_main.yaml \\
TUNING_RUN=results/b_tuning MAIN_RUN=results/b_main ./run_all.sh
```
AWS launch, monitoring and clean-up scripts are in `deployment/` (`aws_launch.sh`, `aws_watch.sh`,
`aws_teardown.sh`, `aws_audit.sh`).

# 9. Presentation talking points
1. Banker's says "safe now". We ask: can we see trouble coming?
2. Show Figure 1: risk score rising, alarm, then unsafe and deadlock a few steps later.
3. No machine learning on purpose: explainable, and a test of whether simple signals are enough.
4. Correctness: safe never coexists with deadlock; unsafe can recover; lead time 0 is a miss; long alarms count
   once; alarms at the end of a cut-off run are excluded.
5. Results: F1 {f2(c.f1)} vs {f2(ov.loc['random', 'f1'])} random and {f2(ov.loc['availability', 'f1'])} free-resource rule;
   median {c.lead_median:.0f} steps of warning; lookahead {f2(lk.f1)} but {look_cost:.0f}× more compute.
6. Scale: {n_seq:,} sequences, {n_steps / 1e6:.0f} million safety checks, run on AWS EC2.
7. Limitations and future work: real traces, learned models, two-stage warning (cheap score first, lookahead only
   when the score is high).
"""
    os.makedirs(os.path.dirname(args.out), exist_ok=True)
    open(args.out, "w").write(md)
    print("report ->", args.out)


if __name__ == "__main__":
    main()
