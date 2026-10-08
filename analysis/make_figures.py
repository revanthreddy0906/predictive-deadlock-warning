"""Phase 14 figures (PDF into paper/figures/), all generated from result files.

    python -m analysis.make_figures --run results/main_test --scaling results/scaling

Colour: fixed categorical order per method (validated palette; CVD-safe on adjacent
pairs). Three hues sit below 3:1 contrast on white, so every line also has a marker
shape and a direct label, and every figure has a matching table in paper/tables/.
`random` is neutral grey: it is a chance reference, not a competing method.
"""

from __future__ import annotations

import argparse
import glob
import json
import os

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from pdw import events, warning

ORDER = ["combined", "need_pressure", "contention", "waiting_ratio", "request_rate", "availability", "lookahead", "random"]
COLOR = dict(zip(ORDER, ["#2a78d6", "#eb6834", "#1baf7a", "#eda100", "#e87ba4", "#008300", "#4a3aa7", "#898781"]))
MARKER = dict(zip(ORDER, ["o", "s", "^", "D", "v", "P", "X", "."]))
LABEL = {"combined": "combined", "need_pressure": "need pressure", "contention": "contention",
         "waiting_ratio": "waiting ratio", "request_rate": "request rate", "availability": "availability",
         "lookahead": "lookahead", "random": "random"}
INK, MUTED, GRID = "#0b0b0b", "#898781", "#e1e0d9"
SCEN = ["normal", "spike", "deadlock_prone"]

plt.rcParams.update({
    "font.size": 8, "axes.titlesize": 9, "axes.labelsize": 8, "legend.fontsize": 7,
    "axes.edgecolor": "#c3c2b7", "axes.labelcolor": INK, "xtick.color": MUTED, "ytick.color": MUTED,
    "axes.grid": True, "grid.color": GRID, "grid.linewidth": 0.5, "axes.axisbelow": True,
    "axes.spines.top": False, "axes.spines.right": False, "lines.linewidth": 1.5,
    "figure.dpi": 150, "savefig.bbox": "tight", "pdf.fonttype": 42,
})


def save(fig, out, name):
    fig.savefig(os.path.join(out, f"{name}.pdf"))
    fig.savefig(os.path.join(out, f"{name}.png"), dpi=200)
    plt.close(fig)


def fig_timelines(run, params, out):
    """Fig 1: example timeline per scenario."""
    best = params["best"]["combined"]
    fig, axes = plt.subplots(3, 1, figsize=(7, 5.4), sharex=False)
    for ax, sc in zip(axes, SCEN):
        files = sorted(glob.glob(os.path.join(run, "traces", f"{sc}_25x8_*.npz"))) or \
            sorted(glob.glob(os.path.join(run, "traces", f"{sc}_*.npz")))
        pick = None
        for f in files:
            d = np.load(f)
            if d["unsafe"].any():
                pick = (f, d)
                break
        if pick is None and files:
            pick = (files[0], np.load(files[0]))
        if pick is None:
            ax.set_visible(False)
            continue
        f, d = pick
        score = warning.risk_score(d["indicators"], best["weights"])
        ev = events.extract(d["unsafe"], d["deadlocked"], "deadlock" if d["deadlocked"].any() else "max_steps")
        alarms = warning.alarm_onsets(score, best["threshold"], best["k"], best["R"], ev.mask)
        t = np.arange(score.size)
        for s, e, _ in ev.episodes:
            ax.axvspan(s, e, color="#e34948", alpha=0.12, lw=0)
        if d["in_spike"].any():
            sp = np.flatnonzero(d["in_spike"])
            ax.axvspan(sp[0], sp[-1] + 1, color="#eda100", alpha=0.12, lw=0)
        ax.plot(t, score, color=COLOR["combined"], lw=1.2)
        ax.axhline(best["threshold"], color=MUTED, ls="--", lw=0.8)
        ax.scatter(alarms, score[alarms], marker="v", s=36, color=INK, zorder=3,
                   edgecolor="white", linewidth=0.8)
        if d["deadlocked"].any():
            ax.axvline(int(np.argmax(d["deadlocked"])), color="#e34948", lw=1.2)
        ax.set_ylim(0, 100)
        ax.set_ylabel("risk score")
        ax.set_title(f"{sc}  ({os.path.basename(f)[:-4]})", loc="left")
    axes[-1].set_xlabel("step")
    fig.text(0.01, -0.02, "Line: combined risk score · dashed: tuned threshold · ▼ alarm onsets · "
             "red band: unsafe episode · red line: deadlock · amber band: spike burst", color=MUTED, fontsize=7)
    fig.tight_layout()
    save(fig, out, "fig1_timelines")


def fig_leads(ev_dir, out):
    """Fig 2: lead-time distributions (captured events only)."""
    df = pd.read_csv(os.path.join(ev_dir, "leads_long.csv"))
    methods = [m for m in ORDER if m in df.method.unique()]
    fig, ax = plt.subplots(figsize=(6.5, 3))
    data = [df[df.method == m].lead.to_numpy() for m in methods]
    bp = ax.boxplot(data, orientation="horizontal", widths=0.5, patch_artist=True, showfliers=False,
                    medianprops={"color": INK, "lw": 1.2}, whiskerprops={"color": MUTED},
                    capprops={"color": MUTED})
    for patch, m in zip(bp["boxes"], methods):
        patch.set_facecolor(COLOR[m])
        patch.set_alpha(0.55)
        patch.set_edgecolor(COLOR[m])
    ax.set_yticks(range(1, len(methods) + 1), [f"{LABEL[m]} (n={len(x)})" for m, x in zip(methods, data)])
    ax.invert_yaxis()
    ax.set_xlabel("lead time (steps before unsafe onset), H_max = 20")
    ax.grid(axis="y", visible=False)
    save(fig, out, "fig2_lead_times")


def fig_pr(ev_dir, out):
    """Fig 3: precision-recall curves (threshold sweep on test, for plotting only)."""
    pr = pd.read_csv(os.path.join(ev_dir, "pr_curves.csv"))
    overall = pd.read_csv(os.path.join(ev_dir, "overall.csv")).set_index("method")
    fig, ax = plt.subplots(figsize=(5.6, 3.8))
    for m in [x for x in ORDER if x in pr.method.unique()]:
        g = pr[pr.method == m].dropna(subset=["precision"]).sort_values("threshold", ascending=False)
        ax.plot(g.recall, g.precision, color=COLOR[m], lw=1.2, marker=MARKER[m], ms=3, label=LABEL[m])
        tuned = g[g.tuned]
        if len(tuned):
            ax.scatter(tuned.recall, tuned.precision, s=70, facecolor=COLOR[m], edgecolor="white", lw=1.5, zorder=4)
    if "random" in overall.index:
        r = overall.loc["random"]
        ax.scatter([r.recall], [r.precision], s=70, color=COLOR["random"], marker="*", zorder=4, label="random (matched rate)")
    ax.set_xlabel("event recall")
    ax.set_ylabel("alarm precision")
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)
    ax.legend(frameon=False, loc="upper left", bbox_to_anchor=(1.02, 1))
    ax.set_title("Threshold sweep · large dots: tuned operating points", loc="left", color=MUTED, fontsize=7)
    save(fig, out, "fig3_pr_curves")


def fig_per_scenario(ev_dir, out):
    """Fig 4: per-scenario F1 with 95% bootstrap CI."""
    df = pd.read_csv(os.path.join(ev_dir, "per_scenario.csv"))
    methods = [m for m in ORDER if m in df.method.unique()]
    fig, axes = plt.subplots(1, 3, figsize=(7, 2.8), sharey=True)
    for ax, sc in zip(axes, SCEN):
        g = df[df.scenario == sc].set_index("method")
        for i, m in enumerate(methods):
            if m not in g.index:
                continue
            r = g.loc[m]
            ax.errorbar(r.f1, i, xerr=[[r.f1 - r.f1_lo], [r.f1_hi - r.f1]], fmt=MARKER[m], color=COLOR[m],
                        ms=5, capsize=2, lw=1.2)
        ax.set_title(sc, loc="left")
        ax.set_xlim(0, 1)
        ax.set_xlabel("F1 (95% CI)")
        ax.grid(axis="y", visible=False)
    axes[0].set_yticks(range(len(methods)), [LABEL[m] for m in methods])
    axes[0].invert_yaxis()
    fig.tight_layout()
    save(fig, out, "fig4_per_scenario_f1")


def fig_hmax(ev_dir, out):
    """Fig 5: H_max sensitivity (same alarms, different horizons)."""
    df = pd.read_csv(os.path.join(ev_dir, "hmax_sensitivity.csv"))
    fig, axes = plt.subplots(1, 2, figsize=(7, 2.8))
    for ax, metric in zip(axes, ["precision", "recall"]):
        for m in [x for x in ORDER if x in df.method.unique()]:
            g = df[df.method == m].sort_values("H_max")
            ax.plot(g.H_max, g[metric], color=COLOR[m], marker=MARKER[m], ms=4, label=LABEL[m])
        ax.set_xscale("log")
        ax.set_xticks([5, 10, 20, 50], ["5", "10", "20", "50"])
        ax.minorticks_off()
        ax.set_xlabel("H_max (steps)")
        ax.set_ylabel(metric)
        ax.set_ylim(0, 1)
    handles, labels = axes[0].get_legend_handles_labels()
    fig.legend(handles, labels, loc="lower center", ncol=4, frameon=False, bbox_to_anchor=(0.5, -0.12))
    fig.tight_layout()
    save(fig, out, "fig5_hmax_sensitivity")


def fig_episodes(ev_dir, out):
    """Fig 6: unsafe-episode outcomes per scenario."""
    df = pd.read_csv(os.path.join(ev_dir, "episode_outcomes.csv")).set_index("scenario").reindex(SCEN).fillna(0)
    fig, ax = plt.subplots(figsize=(4.6, 2))
    y = np.arange(len(df))
    rec = df.recovered_frac.fillna(0).to_numpy()
    dead = df.deadlocked_frac.fillna(0).to_numpy()
    ax.barh(y, rec, color="#2a78d6", height=0.55, label="recovered to safe")
    ax.barh(y, dead, left=rec, color="#e34948", height=0.55, label="ended in deadlock",
            edgecolor="white", linewidth=2)
    for i, sc in enumerate(df.index):
        tot = int(df.loc[sc, "ep_recovered"] + df.loc[sc, "ep_deadlocked"])
        ax.text(1.02, i, f"{dead[i]:.0%} deadlock (n={tot})", va="center", fontsize=7, color=INK)
    ax.set_yticks(y, df.index)
    ax.set_xlim(0, 1)
    ax.invert_yaxis()
    ax.set_xlabel("fraction of resolved unsafe episodes")
    ax.legend(frameon=False, ncol=2, loc="lower left", bbox_to_anchor=(0, 1.0))
    ax.grid(axis="y", visible=False)
    save(fig, out, "fig6_episode_outcomes")


def fig_scaling(sc_dir, out):
    """Fig 7 + 8: time per safety check vs n (log-log), vectorised vs reference speed-up."""
    df = pd.read_csv(os.path.join(sc_dir, "scaling.csv"))
    fits = pd.read_csv(os.path.join(sc_dir, "scaling_fits.csv"))
    ms = sorted(df.m.unique())
    cols = ["#2a78d6", "#eb6834", "#1baf7a"]
    fig, axes = plt.subplots(1, 2, figsize=(7, 2.9))
    for ax, col, title in zip(axes, ["vectorised_us_random_states", "reference_us_random_states"],
                              ["vectorised (NumPy)", "reference (plain loops)"]):
        for c, m, mk in zip(cols, ms, ["o", "s", "^"]):
            g = df[df.m == m].sort_values("n")
            slope = fits[(fits.metric == col) & (fits.m == m)].slope_log_n.iloc[0]
            ax.plot(g.n, g[col], color=c, marker=mk, ms=4)
            ax.annotate(f"m={m} (slope {slope:.2f})", (g.n.iloc[-1], g[col].iloc[-1]), xytext=(4, 0),
                        textcoords="offset points", fontsize=6, va="center")
        ax.set_xscale("log")
        ax.set_yscale("log")
        ax.set_xlabel("processes n")
        ax.set_ylabel("µs per safety check")
        ax.set_title(title, loc="left")
    fig.tight_layout()
    save(fig, out, "fig7_scaling")

    fig, ax = plt.subplots(figsize=(4.6, 2.6))
    for c, m, mk in zip(cols, ms, ["o", "s", "^"]):
        g = df[df.m == m].sort_values("n")
        ax.plot(g.n, g.speedup, color=c, marker=mk, ms=4)
        ax.annotate(f"m={m}", (g.n.iloc[-1], g.speedup.iloc[-1]), xytext=(4, 0), textcoords="offset points",
                    fontsize=6, va="center")
    ax.set_xscale("log")
    ax.set_xlabel("processes n")
    ax.set_ylabel("speed-up (reference / vectorised)")
    save(fig, out, "fig8_speedup")


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--run", default="results/main_test")
    ap.add_argument("--params", default="results/tuning/best_params.json")
    ap.add_argument("--scaling", default="results/scaling")
    ap.add_argument("--out", default="paper/figures")
    args = ap.parse_args(argv)
    os.makedirs(args.out, exist_ok=True)
    ev_dir = os.path.join(args.run, "eval")
    params = json.load(open(args.params))
    fig_timelines(args.run, params, args.out)
    fig_leads(ev_dir, args.out)
    fig_pr(ev_dir, args.out)
    fig_per_scenario(ev_dir, args.out)
    fig_hmax(ev_dir, args.out)
    fig_episodes(ev_dir, args.out)
    if os.path.exists(os.path.join(args.scaling, "scaling.csv")):
        fig_scaling(args.scaling, args.out)
    print("figures written to", args.out)


if __name__ == "__main__":
    main()
