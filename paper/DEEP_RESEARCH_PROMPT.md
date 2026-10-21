# Deep research prompt: Predictive Deadlock Warning

Copy everything below the line into a deep-research tool.

---

You are a research assistant helping two undergraduate students (Operating Systems course, CBIT Hyderabad) turn a completed experimental project into a full research paper (IEEE conference style, about 8–10 pages). Do a thorough, citation-backed literature review and positioning analysis. Accuracy matters more than volume: **only cite sources you have actually found and can link to. Never invent authors, titles, venues, years, DOIs or numbers.** If you are unsure about a detail, mark it "UNVERIFIED".

## 1. Our project (context; do not research this part, use it to judge relevance)

**Research question.** Banker's algorithm (Dijkstra, EWD108, 1965) tells an OS whether the current resource-allocation state is *safe* right now; it gives no signal that the system is drifting towards an unsafe state. We ask: can simple, explainable indicators computed from the allocation state and the recent request stream raise an alarm **before** Banker's algorithm reports an unsafe state, how early, and how reliably?

**What we built.**
- An **observer-mode** simulator. Every valid request is granted, even unsafe ones. Banker's safety check and deadlock detection run after every step only to *observe*, so the system can actually become unsafe.
- Three workloads: *normal*, *spike* (sudden broad resource grabs), and *deadlock-prone* (circular resource preference).
- Claim tightness (sum of maximum claims ÷ total units) is the calibration parameter.
- A rule-based (no ML) early-warning score, a weighted mean of five indicators in [0, 1]:
  - scarcity;
  - need pressure, ΣNeed / (ΣNeed + Available);
  - contention, the share of resource types where ≥2 processes need more than is free;
  - waiting ratio;
  - request-rate acceleration.
- An alarm fires when the score is ≥ threshold for k consecutive steps, followed by a refractory period of R steps.
- Event-based evaluation borrowed from early-warning research:
  - alarm precision, event recall, F1 and lead time;
  - an alarm at the onset step counts as a miss;
  - censoring at the end of a run;
  - flicker-merged episodes;
  - stratified bootstrap 95% confidence intervals.
- Baselines:
  - random alarms at a matched rate;
  - a free-resource ("availability") threshold;
  - each single indicator alone;
  - an exact one-step **lookahead**: the fraction of running processes whose largest feasible grant would make the state unsafe, costing one safety check per process per step.
- Disjoint tuning and test seeds.

**Scale.** 300,000 simulated sequences (676 million requests, each followed by a Banker's check); 3 scenarios × 5 sizes (10–200 processes, 5–20 resource types). Run on one AWS EC2 c7i.8xlarge (32 vCPU) in 2 h 43 min.

**Key results (test split, 20-step warning window).**

| Method | F1 |
|---|---|
| Combined score | 0.28 (precision 0.24, recall 0.34, median lead 10 steps) |
| Contention alone | 0.34 |
| Availability threshold | 0.16 |
| Random | 0.006 |
| Exact lookahead | 0.74 (on the subset where computed) |

- Lookahead's lead time is similar to ours on jointly caught events, but it costs ~39× the simulation's compute at 200 processes.
- Spikes are easiest (F1 0.42); gradual build-ups are hardest (~0.22).
- 77–100% of unsafe episodes ended in deadlock.
- The vectorised NumPy safety check was 1.3×–7.7× faster than the textbook loop. Measured growth with n was far below Θ(mn²).

## 2. What to research

For every item, give the key findings and **full citations with a DOI or a stable URL**.

**A. Classical foundations**
1. Banker's algorithm: Dijkstra's original (EWD108 / EWD623) and Habermann's 1969 "Prevention of system deadlocks". Exact definitions of safe/unsafe states.
2. Coffman, Elphick & Shoshani (1971), "System Deadlocks": the four conditions. Holt (1972) resource-allocation graphs.
3. Standard textbook treatment (Silberschatz, Galvin & Gagne; Tanenbaum). Cite edition and year.
4. Complexity of the safety check, Θ(mn²), and improved variants: incremental or amortised O(mn) versions (e.g. Kessels-style, BIT Numerical Mathematics) and DBDAA (Zohora, Farhin & Kaiser, PLOS ONE 2024, doi:10.1371/journal.pone.0310807). **Verify the BIT paper's exact authors, title, year and DOI (possibly 10.1007/BF01933724).**

**B. Deadlock detection, avoidance and prediction (closest related work)**
5. Deadlock detection algorithms and their cost; detection vs avoidance vs prevention trade-offs in modern systems (databases, distributed systems, cloud schedulers, GPU/HPC resource managers).
6. **Deadlock prediction / forecasting:** any work predicting deadlocks or unsafe states before they occur. This includes ML-based work (e.g. Le Ngoc & Tran Cong, INISCOM 2023, linear regression in CloudSim; RL or AI-based thread-deadlock prediction, e.g. EasyChair preprint 14955, 2024), runtime-monitoring approaches and static-analysis tools (e.g. dynamic deadlock prediction in Java/C programs, such as lock-graph or "predictive analysis" tools). Clearly distinguish *thread/lock deadlock prediction in programs* from *resource-allocation deadlock in an OS/scheduler*.
7. Any prior work using **indicators, metrics or risk scores** of resource pressure or contention to anticipate deadlock or starvation.
8. Lookahead or "one-step" safety checks, and multi-step or probabilistic avoidance (e.g. probabilistic Banker's variants, approaches without known maximum claims).

**C. Early-warning evaluation methodology (to justify our metrics)**
9. Event-based evaluation of early-warning and alarm systems: alarm precision vs event recall, lead time, refractory/suppression periods, why warnings at or after onset count as misses, matched-rate random baselines, censoring. Sources from clinical deterioration (e.g. Hyland et al., Nature Medicine 2020), earthquake early warning (e.g. Münchmeyer et al., TEAM, arXiv:2009.06316), predictive maintenance / failure prediction, and anomaly detection (e.g. range-based precision/recall, NAB scoring).
10. Why precision–recall is preferred over ROC/accuracy for rare events (e.g. Saito & Rehmsmeier 2015; Davis & Goadrich 2006).
11. Bootstrap confidence intervals for classification metrics (Efron & Tibshirani), and stratified resampling.

**D. Systems context and motivation**
12. Real-world incidents or studies where deadlocks or resource exhaustion caused outages (databases, Kubernetes/cloud schedulers, distributed locks), to motivate early warning.
13. Alerting practice in SRE/monitoring (alert fatigue, precision of alerts, e.g. Google SRE book), to connect our false-alarm analysis to industry.
14. Failure prediction in large-scale systems (e.g. Salfner, Lenk & Malek 2010, "A survey of online failure prediction methods", ACM Computing Surveys).

**E. Methodology support**
15. Simulation-based evaluation in OS/resource-management research: good practice, reproducibility, synthetic workloads and their validity threats.
16. Known limitation: Banker's algorithm requires known maximum claims. Find work discussing this and estimating claims in practice.

## 3. Critical analysis we need

- **Novelty check.** Based on what you find, state clearly and honestly whether our combination is novel: a rule-based indicator score + observer-mode simulation + event-based early-warning evaluation + lookahead baseline for *resource-allocation* deadlock. List the 3–5 closest prior works and exactly how we differ.
- **Reviewer objections.** The strongest objections a reviewer would raise (e.g. circularity between indicators and Banker's check, synthetic workloads, known maximum claims, moderate F1), with literature-backed ways to address each.
- **Possible improvements.** Additional analyses or baselines the literature suggests we should add (e.g. other avoidance heuristics, learned models on our data, cost-aware metrics), with the source for each suggestion.

## 4. Output format

1. **Executive summary** (≤ 300 words).
2. **Annotated bibliography** grouped by sections A–E. For each source:
   - full citation (authors, title, venue, year);
   - DOI or URL;
   - 2–3 sentences on what it says;
   - 1 sentence on how it relates to our paper;
   - a tag: [FOUNDATIONAL] / [CLOSEST RELATED] / [METHOD SUPPORT] / [MOTIVATION].
3. **Related-work narrative**: 600–900 words of draft text, in academic style, positioning our work, with in-text citation keys.
4. **Novelty and gap statement**: one paragraph.
5. **Reviewer objections and responses**: a table.
6. **Suggested improvements**: a prioritised list.
7. **BibTeX** for every cited source (only verified ones).
8. **"To verify" list**: anything you could not fully confirm.

Prefer peer-reviewed sources (ACM, IEEE, USENIX, Springer, Elsevier) and authoritative textbooks. Use preprints only where nothing peer-reviewed exists, and label them as preprints.
