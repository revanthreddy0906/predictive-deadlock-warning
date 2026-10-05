# Predictive Deadlock Warning: Full Case Study Context

> Part 1 of this document is the complete background: what the case study is, why it exists, every decision made and why. Part 2 is the complete implementation plan (unchanged from `IMPLEMENTATION_PLAN.md`). Give this whole file to Claude Code or to a teammate who needs the full picture.

---

# PART 1: CONTEXT

## 1.1 Course and Logistics

| Item | Detail |
|---|---|
| Course | Operating Systems, CBIT (Information Technology) |
| Component | Internal case study, 15 marks |
| Team | Revanth Reddy Lingala and Sujju (2 members) |
| Faculty requirement | Implementation must run on a **server / cloud** |
| Our interpretation | Headless experiments on **AWS EC2**, results written up as a **research paper**. No frontend |
| Target submission | October 10, 2026 |
| Syllabus mapping | Unit IV (Concurrency, Synchronization, **Deadlocks**: RAG, prevention, avoidance, recovery), with links to Unit II (process management) |

**Note on the allotment sheet:** the official allotment PDF lists our team (S.No 22) under the earlier topic *"Memory Management Simulator: Page Replacement and Allocation Strategy Analysis"*. We later changed to the deadlock topic. Confirm with the faculty that the allotment record is updated to the new title.

## 1.2 How We Got Here (decision history)

1. **First idea:** Memory management simulator (page replacement FIFO/LRU/Optimal + First/Best/Worst Fit allocation, RAM/SSD/page-table model). Submitted in the form initially.
2. **Problem found after reviewing all 37 allotted case studies:** heavy overlap. Team 9 (browser memory, FIFO/LRU/Optimal) and Team 26 (ML-assisted page replacement) cover the same ground. Our version was an implementation exercise with no research question.
3. **Requirement:** a topic with a genuine research angle, not just "implement and compare algorithms".
4. **Options considered:** predictive page replacement (needs model fitting), deadlock prediction (classical, no ML), empirical study of scheduling assumptions.
5. **Chosen:** deadlock prediction. Six other teams do deadlocks, but all of them only **detect or avoid** (Banker's, detection and recovery). Nobody asks whether an unsafe state can be **anticipated earlier**.
6. **Faculty asked for a server/cloud implementation.** We chose headless batch experiments on EC2 instead of a web app.
7. **Sujju drafted a full plan** (React dashboard, FastAPI, EC2, 20 phases). Reviewed; design flaws fixed (Section 1.8).
8. **Literature research** done; evaluation method and case handling rebuilt on established early-warning practice (Part 2, Sections 2 and 3).

## 1.3 The Problem in Simple Terms

Many processes share limited resources (CPU slots, memory blocks, devices, files). If they request resources in a bad order, they can end up waiting on each other forever. That is a **deadlock**.

**Banker's Algorithm** (Dijkstra, 1965) checks the current state and answers: *if every process asked for the maximum it might still need, is there some order in which all of them could finish?* If yes, the state is **safe**. If no, it is **unsafe**.

The limitation: Banker's only answers **"safe right now?"**. It gives no signal that the system is **drifting toward** danger.

**Our question:** By watching simple signals from the allocation state and the pattern of requests (how scarce resources are, how much demand is outstanding, how many processes are blocked, how fast requests are arriving), can we raise an alarm **before** Banker's reports unsafe? How early, and how reliably?

Analogy: Banker's is the fire alarm. We are testing whether a smoke detector can go off a few steps earlier, and how often it gives false alarms.

## 1.4 Key Concepts (glossary)

| Term | Meaning in this project |
|---|---|
| Process | A simulated program holding and requesting resource units |
| Resource type | A kind of resource (e.g., R0, R1, R2) with a fixed number of units |
| Max claim | Most units of each resource a process may ever hold |
| Allocation | Units a process currently holds |
| Need | `max_claim - allocation`, what it may still request |
| Available | Units not held by anyone |
| Safe state | Banker's finds an order in which all processes can finish |
| Unsafe state | No such order exists. **Not necessarily a deadlock**: processes might still finish if they don't request their full claims |
| Deadlock | Some waiting processes can never be satisfied even if everyone else finishes. Always unsafe. Safe and deadlocked together is impossible |
| Observer mode | Our simulator grants every valid request and only uses Banker's to **observe** safety. Without this the system would never become unsafe and nothing could be measured |
| Indicator | A number in [0, 1] computed each step (scarcity, need pressure, contention, waiting ratio, request rate) |
| Risk score | Weighted combination of indicators, 0 to 100 |
| Alarm | Fires when the risk score stays above a threshold for k steps |
| Refractory period | After an alarm, no new alarm for R steps, so a long high-risk stretch counts once |
| Unsafe onset | A step where the state turns from safe to unsafe |
| Lead time | Unsafe onset step minus the alarm step that preceded it |
| Alarm precision | Fraction of alarms followed by a real unsafe onset within the horizon |
| Event recall | Fraction of unsafe onsets that had a valid earlier alarm |
| Baseline | A deliberately simple method (low-availability rule, random alarms) our method must beat |

## 1.5 The Research Angle (and honest novelty)

**What already exists:**
- Banker's Algorithm and deadlock detection: classical (Dijkstra 1965; standard OS textbooks).
- Faster Banker's variants: amortised O(mn) modification; DBDAA (PLOS ONE 2024) with O(nd) average case.
- **Deadlock prediction with machine learning:** linear regression on cloud VMs in CloudSim (INISCOM 2023); RL and AI-based thread-deadlock prediction (2024 preprints).

So "predict deadlock" is **not new at field level**. We do not claim it is.

**What we contribute (defensible novelty):**
1. **Rule-based, fully explainable early-warning algorithm, no ML.** We test whether simple indicators give useful warning without training a model. A "do we even need ML?" question.
2. **Controlled synthetic scenarios** (normal, sudden spike, gradual deadlock-prone build-up) to isolate which kind of build-up is easiest or hardest to anticipate.
3. **Event-based evaluation borrowed from early-warning research** (clinical, earthquake, equipment failure): alarm precision, event recall, lead-time distributions, censoring, refractory periods. Most deadlock work does not evaluate warnings this rigorously.
4. **Explicit baselines** (availability threshold, random alarms at matched rate, single indicators), so results show real value rather than built-in correlation.
5. **Separating "unsafe" from "deadlocked"**: we measure how often unsafe states actually become deadlocks and whether alarms anticipate either.
6. **Scaling study on cloud hardware**: measured runtime growth versus the Θ(m·n²) theory.

**How to say it:** *"We are not using machine learning. We designed and evaluated a lightweight, rule-based early-warning algorithm that computes resource-pressure indicators at each step and raises alarms before Banker's Algorithm detects an unsafe state, and we measure its lead time, precision and recall against baselines."*

## 1.6 Proof of Concept vs Proof of Work

| | Proof of Concept | Proof of Work |
|---|---|---|
| Question | Does the idea work at all? | Does it hold up systematically, at scale? |
| Form | One small hand-checked sequence (5 processes, 3 resources) shown as a step table: risk score rising, alarm, then Banker's flips to UNSAFE | Hundreds of thousands of sequences on EC2 across scenarios and sizes, with precision, recall, lead-time distributions, confidence intervals, baselines |
| Use | Opening slide / first figure, so anyone understands the idea | Results section of the paper |

## 1.7 Expected Outcomes

- A tested Python engine: state model, Banker's (vectorised + reference), deadlock detection, scenario generators, indicators, alarm logic, event-based metrics.
- Large-scale experiment results generated on AWS EC2 (dataset produced by our own simulator, not downloaded).
- Answers to RQ1 to RQ7 with figures and tables: lead time, precision/recall, best indicators, per-scenario behaviour, unsafe vs deadlock outcomes, scaling.
- An IEEE-style research paper (6 to 8 pages), GitHub repo with reproduction instructions, and a presentation.
- **Any result is valid.** "Indicators give 3 steps of warning with 70% precision" and "indicators barely beat the availability baseline" are both legitimate findings if measured honestly.

## 1.8 Fixes Applied to the Earlier Draft Plan

| Issue in earlier draft | Why it was a problem | Fix |
|---|---|---|
| Banker's used to **reject** unsafe requests | System never becomes unsafe, so lead time can't be measured and every warning becomes a false positive | **Observer mode**: grant valid requests, Banker's only observes |
| No baseline | Indicators read the same state Banker's reads, so some correlation is guaranteed | Availability and random baselines, single-indicator ablations |
| Per-step false positives | One long warning counted as dozens of false alarms | Event-based metrics with refractory period |
| Accuracy as headline | Most steps are safe; "never warn" scores high accuracy | Alarm precision, event recall, F1, lead time |
| Tuning and reporting on same data | Overfitting | Disjoint tuning and test seed ranges |
| Request frequency with one request per step | Constant, meaningless | Rate defined as change in requested units across sliding windows |
| Waiting ratio with no waiting rule | Always zero | Request > available puts process into WAIT |
| 1,000 processes, 100,000 requests | Θ(m·n²) per check makes this infeasible | Tens to low hundreds of processes; report scaling curve |
| React dashboard, FastAPI, Nginx | Large time cost, not required | Headless runs on EC2, paper as deliverable |
| Unsafe treated as deadlock | Unsafe states can recover | Separate unsafe and deadlocked targets |

## 1.9 Form Text (for the deadlock topic)

**Title:** Predictive Deadlock Warning: Early Detection of Unsafe States from Resource-Request Patterns

**Objectives:** To investigate whether resource-request patterns can give early warning of an approaching unsafe state before Banker's Algorithm detects it. This involves building a resource-allocation simulator with Banker's safety check and deadlock detection, generating controlled workload scenarios (normal, sudden spike, gradual deadlock-prone build-up), designing a rule-based early-warning algorithm from explainable indicators, and evaluating its lead time, alarm precision and event recall against baselines through large-scale experiments on a cloud server.

**Career relevance:** Deadlock handling and resource management are core OS topics in interviews for backend, systems and infrastructure roles. Formulating and testing a research question, designing controlled experiments, running them at scale on cloud infrastructure and reporting results with proper metrics builds research and systems-engineering skills beyond implementing textbook algorithms.

**Tangible outcome:** A tested simulation and early-warning engine, large-scale experimental results generated on AWS EC2, comparative analysis of indicators and baselines (lead time, precision, recall, scaling behaviour), a research paper, and a public GitHub repository with reproduction instructions.

**Milestones:** Oct 1 to 3: core engine (state model, Banker's, detection, scenarios, indicators, metrics) with tests. Oct 4 to 6: calibration, tuning and main experiments on AWS EC2. Oct 7 to 9: analysis, figures and paper writing. Oct 10: submission and presentation.

## 1.10 Presentation Talking Points

1. Banker's tells you "safe now". We ask: can we see trouble coming?
2. PoC slide: one 5x3 sequence, risk rising, alarm, then UNSAFE a few steps later.
3. Why no ML: explainability; testing whether simple signals are enough.
4. Correctness highlights: safe never coexists with deadlock (property test); unsafe can recover; lead time 0 counts as a miss; persistent alarms count once; censored alarms excluded.
5. Results vs baselines, per scenario (spike vs gradual).
6. Scale: total sequences and steps run on EC2, scaling curve vs Θ(m·n²).
7. Honest limitations and future work.

## 1.11 Status Check (as of October 3)

Per the timeline, by end of Oct 3 the following should be done: Phase 1 (state), Phase 2 (Banker's + detection, all tests passing), Phase 3 (scenarios), Phase 4 (simulator), Phase 5 (indicators), Phase 6 (alarm logic), Phase 7 (events/metrics), and a local smoke run. If anything earlier is incomplete, use the fallback in Part 2, Section 7 rather than skipping tests.

---

# PART 2: COMPLETE IMPLEMENTATION PLAN

# Predictive Deadlock Warning: Research-Backed Implementation Plan (v2)

**Title:** Predictive Deadlock Warning: Early Detection of Unsafe States from Resource-Request Patterns
**Team:** Revanth, Sujju
**Deliverable:** Headless experiment engine run on AWS EC2 + research paper (no frontend)
**Deadline target:** October 10, 2026

> Hand this file to Claude Code. Build strictly phase by phase. Do not start a phase until the previous phase's tests pass. Section 2 (research) and Section 3 (case analysis) define the rules the code must follow.

---

## 1. Project Summary

Banker's Algorithm answers one question: *is the system safe right now?* It gives no signal that the system is drifting toward danger.

We design a **rule-based (non-ML) early-warning algorithm** that computes simple, explainable indicators from the allocation state and request history, combines them into a risk score, and raises alarms. Banker's safety check is the **ground truth**. A separate deadlock-detection check gives a second, stricter target. We measure how early and how reliably alarms fire before these events, and compare against baselines.

Experiments run headless on AWS EC2 at large scale. Results are analysed offline and written up as a paper.

### Research Questions

| ID | Question |
|---|---|
| RQ1 | Can indicators computed from resource-request patterns give early warning of an unsafe state? |
| RQ2 | How much lead time do alarms provide? |
| RQ3 | What are alarm precision and event recall? |
| RQ4 | Which indicators contribute most, and does the combined score beat simple baselines? |
| RQ5 | How does warning quality vary across workload scenarios? |
| RQ6 | How often do unsafe states actually become deadlocks, and can alarms anticipate deadlocks too? |
| RQ7 | How does runtime scale with processes and resources? |

---

## 2. Research Findings That Shape the Design

### 2.1 Banker's Algorithm cost
- The standard safety algorithm is **Θ(m·n²)** for n processes and m resource types. Space is O(m·n). Source: Dijkstra, EWD108 (1965); MIT Algorithm Wiki; Kessels-style modification (BIT, 1990s) achieves amortised O(mn) under likely conditions and is at worst about 2x faster.
- A 2024 PLOS ONE paper (DBDAA, Zohora et al.) reports O(n) best case and O(nd) average/worst case by dynamically including processes in safety checks, versus O(n²d) for the original.
- **Design impact:** safety checks dominate runtime. Vectorise with NumPy. Keep process counts in tens to low hundreds. Report a scaling curve rather than claiming huge process counts. Mention DBDAA/Kessels-style incremental checks as future work.

### 2.2 Unsafe is not deadlock
- An unsafe state is not necessarily deadlocked; processes may still all terminate if they don't request up to their full claims. A state can be: safe and not deadlocked; unsafe and deadlocked; unsafe and not deadlocked; but **never safe and deadlocked**. Source: NYU OS lecture notes (Gottlieb), UIUC CS241.
- Banker's makes the **most pessimistic** assumption (each process may request its full remaining claim). Deadlock detection makes the **most optimistic** assumption (running processes will release everything and finish).
- **Design impact:**
  - Record both `unsafe` and `deadlocked` per step.
  - Primary target = unsafe onset (what Banker's detects). Secondary target = deadlock onset.
  - Invariant test: `deadlocked => unsafe` must always hold. Any violation is a bug.
  - Unsafe states can **recover** to safe in observer mode (a process finishes). The evaluation must handle multiple unsafe episodes per sequence.

### 2.3 Prior work on deadlock prediction
- Le Ngoc & Tran Cong (INISCOM 2023, Springer): linear regression (Weka) to forecast deadlock possibility in cloud VMs, evaluated in CloudSim against FCFS, Round Robin, MaxMin, MinMin.
- Other work uses reinforcement learning and AI-based predictive systems for thread deadlocks (e.g., EasyChair preprint 14955, 2024).
- **Design impact / novelty:** we do **not** train a model. Our contribution is a lightweight, explainable, rule-based warning algorithm, evaluated on controlled synthetic scenarios with event-based metrics and explicit baselines. Related Work section must cite these and position our work honestly.

### 2.4 How early-warning systems are evaluated
Early-warning literature (clinical deterioration, earthquake early warning, equipment failure, disease risk) converges on **event-based** evaluation, not per-sample classification:
- **Alarm precision** = true alarms / total alarms.
- **Event recall** = captured events / total events. Only the first alarm before an event counts; repeated alarms in the same episode are ignored.
- A warning issued **at or after** the event onset counts as a **miss**, not a hit (earthquake warning convention).
- A continuous stretch of high score with no event in the following horizon counts as **one** false alert, regardless of duration.
- **Lead time** = event onset time minus first valid alarm time. When comparing methods, compare lead times on events that **both** methods caught.
- Valid warnings fall inside a window before the event, e.g. `[d - H_max, d - H_min]`.
- Precision-recall curves are preferred over ROC for imbalanced event data; thresholds must be chosen on a training split and evaluated on a separate test split.
- A **random alarm baseline** at a matched alarm rate is standard.

**Design impact:** Section 3.5 defines our metrics exactly this way.

---

## 3. Case Analysis

Every case the simulator and evaluator can hit, with the required handling.

### 3.1 System-state cases

| Case | Possible? | Handling |
|---|---|---|
| Safe, not deadlocked | Yes | Normal operation |
| Unsafe, not deadlocked | Yes (common) | Primary target event. May recover to safe later |
| Unsafe, deadlocked | Yes | Secondary target event. Terminal unless recovery is modelled |
| Safe, deadlocked | **No** | Assert in tests; indicates a bug |
| Initial state unsafe | Excluded | Regenerate initial state until safe. Sequences start safe |
| All processes finished | Yes | State trivially safe. End sequence early (`ended_all_finished`) |

### 3.2 Request cases

| Case | Handling |
|---|---|
| Zero vector request | Skip generation; generators must produce non-zero requests |
| Request > remaining need | Invalid. Generators clip to need; if still produced, log `EXCEEDS_NEED` and skip |
| Request > max claim at init | Impossible if state built correctly; validate at construction |
| Request <= need, <= available | **GRANT** (observer mode: granted even if resulting state is unsafe) |
| Request <= need, > available | **WAIT**: process blocked, request stored as pending |
| Request from a waiting process | Not generated; a waiting process issues no new request until its pending one is granted |
| Request from a finished process | Not generated |
| Pending request becomes satisfiable | At the start of each step, retry waiting processes (FIFO order) |

### 3.3 Process lifecycle cases

| Case | Handling |
|---|---|
| Need becomes zero | Process finishes, releases full allocation, marked finished |
| Voluntary partial release | Allowed with small probability in `normal` scenario only (config) |
| All waiting and none satisfiable | This is deadlock among waiting processes; recorded by detection check |
| New process arrival | Out of scope (fixed process set). Listed as limitation |
| Deadlock recovery (killing a process) | Out of scope for main runs. When deadlock is detected, sequence ends (`ended_deadlock`) |

### 3.4 Scenario cases

| Scenario | Expected behaviour | Evaluation role |
|---|---|---|
| `normal` | Small balanced requests, frequent completions, releases. Unsafe states rare | Measures **false alarm** behaviour |
| `spike` | Normal traffic, then a burst of large requests from several processes | Tests reaction to **sudden** change; lead time expected short |
| `deadlock_prone` | Process i prefers resource (i+1) mod m, gradual growth, rare completions | Tests **gradual** build-up; lead time expected longer |

Report the **fraction of sequences with at least one unsafe onset** per scenario (class balance). If `deadlock_prone` is almost always unsafe from the start, or `normal` never goes unsafe, tune generator parameters on tuning seeds until each scenario gives a meaningful mix.

### 3.5 Evaluation cases (event-based)

Definitions (per sequence):
- `score[t]` = risk score after processing step t.
- **Alarm onset** at step t: `score[t] >= threshold` held for `k` consecutive steps ending at t, and no alarm onset in the previous `R` steps (refractory period, default R = H_max).
- **Unsafe onset** at step d: `unsafe[d] == True` and `unsafe[d-1] == False`.
- **Valid window** for event d: `[d - H_max, d - H_min]` with default `H_min = 1`, `H_max = 20` (configurable; also report H_max in {5, 10, 50}).

| Case | Label |
|---|---|
| Alarm onset in valid window of an unsafe onset | True alarm; event captured |
| Alarm fires at the same step as unsafe onset (lead 0) | **Miss** (detection, not prediction) |
| Alarm fires after unsafe onset, during the unsafe episode | Ignored for precision (system already unsafe); event counts as missed if no earlier valid alarm |
| Alarm onset with no unsafe onset in `(t, t + H_max]` | False alarm |
| Unsafe onset with no alarm in its valid window | Missed event |
| Several alarm onsets before one event | First valid one gives lead time; others in window are not extra true alarms |
| One alarm before several events within H_max | Counts for the first event only |
| Score high continuously, no event | One false alarm per refractory period |
| Sequence with no alarms and no events | Contributes nothing to precision/recall; counted in "quiet sequences" |
| Alarm in last H_max steps of sequence (future unknown) | **Censored**: excluded from precision |

Metrics:
- `alarm_precision = true_alarms / (true_alarms + false_alarms)`
- `event_recall = captured_events / total_events`
- `F1` of the two
- `false_alarms_per_1000_steps`
- `lead_time`: mean, median, IQR, distribution; plus fraction of captured events with lead >= {1, 3, 5, 10}
- Pairwise lead-time comparison between methods only on events both captured
- Same metrics repeated with **deadlock onset** as the target (RQ6)
- Also report: fraction of unsafe episodes that end in deadlock vs recover to safe
- 95% bootstrap confidence intervals (resample sequences, 1,000 resamples)
- **No accuracy headline.**

### 3.6 Indicator cases

| Case | Handling |
|---|---|
| No active processes | All indicators = 0 |
| `sum(total) == 0` for a resource | Excluded at construction (every resource has >= 1 unit) |
| `available[j] == 0` | Use `eps` in denominators, clip results to [0, 1] |
| Window shorter than W at start | Use available history; `request_rate = 0` until 2 windows exist |
| Indicator mathematically close to Banker's check | Expected for `need_pressure`. Discuss as circularity threat; baselines expose it |

### 3.7 Baseline cases

| Baseline | Definition | Purpose |
|---|---|---|
| `availability` | alarm when `sum(available)/sum(total) < t_a` | Trivial single-signal rule |
| `random` | alarm onsets at random steps with the same rate as `combined` on that sequence | Chance level |
| `need_pressure_only` | single indicator | Tests whether combining adds value |

Thresholds for every method (including baselines) are tuned on the tuning split, same objective.

### 3.8 Data split and reproducibility cases

| Case | Handling |
|---|---|
| Tuning vs test leakage | Tuning seeds 0 to 1,999; test seeds 100,000+. Never overlap |
| Changing generator after seeing test results | Not allowed. If a bug forces a change, re-run tuning and test, and note it |
| Non-determinism | Pass `numpy.random.Generator(seed)` explicitly; no global RNG |
| Crashed batch run | Chunked output + resume by config hash |

### 3.9 Performance cases

| Case | Handling |
|---|---|
| Safety check every step too slow at n = 100, m = 20 | Vectorised NumPy check; profile first |
| Deadlock detection cost | Run every step only for n <= 50; else every `c` steps (config), and at every step where `waiting` changed |
| Traces too large | Store per-step traces only for a small subset of seeds; store event lists (onsets) for all |
| Memory on EC2 | Write results in chunks (Parquet); workers return compact summaries |

### 3.10 Edge Case Test Matrix (consolidated)

Every row below must have a dedicated unit test or invariant check. This is the checklist Claude Code works through.

#### A. System state (`test_state.py`, `test_banker.py`)

| # | Edge case | Expected / tested behaviour |
|---|---|---|
| A1 | **Safe AND deadlocked** | Impossible. Property test on 2,000 random states asserts `deadlocked => unsafe`. Violation = bug |
| A2 | **Unsafe but NOT deadlocked** | Must be possible and recorded separately from deadlock |
| A3 | Initial state unsafe | Rejected; regenerate until safe; raise after max attempts |
| A4 | All processes finished | Trivially safe; sequence ends with `ended_all_finished` |
| A5 | Conservation violated | `available + allocation.sum(0) == total` checked every step in debug mode |
| A6 | Finished process still holding resources | `validate()` fails |
| A7 | Vectorised Banker's disagrees with reference | Compared on 2,000 random states; must match exactly |
| A8 | Textbook ground truth | Silberschatz 5x3 is SAFE with valid sequence; 7A/2B/6C detection example: not deadlocked, then deadlocked after P2 requests one more C |

#### B. Requests (`test_banker.py`, `test_scenarios.py`)

| # | Edge case | Expected / tested behaviour |
|---|---|---|
| B1 | Zero-vector request | Never generated |
| B2 | Request > remaining need | Clipped by generator; if it slips through, `EXCEEDS_NEED` logged and skipped |
| B3 | Request <= need but > available | `WAIT`: process blocked, request stored as pending |
| B4 | **Request that makes state unsafe** | Still granted (observer mode, intentional) |
| B5 | New request from a waiting process | Never generated |
| B6 | Request from a finished process | Never generated |
| B7 | Pending request becomes satisfiable | Retried at start of each step, FIFO order |
| B8 | No process able to request | Generator returns `None`; sequence ends |

#### C. Process lifecycle (`test_simulator.py`)

| # | Edge case | Expected / tested behaviour |
|---|---|---|
| C1 | Need reaches zero | Process finishes and releases full allocation |
| C2 | All processes waiting, none satisfiable | Detected as deadlock; sequence ends with `ended_deadlock` |
| C3 | **Unsafe state recovers to safe** | Allowed; multiple unsafe episodes per sequence supported |
| C4 | Same seed run twice | Identical output (determinism) |
| C5 | Deadlock step | `unsafe` is also True on that step |

#### D. Indicators (`test_indicators.py`)

| # | Edge case | Expected / tested behaviour |
|---|---|---|
| D1 | No active processes | All indicators = 0 |
| D2 | `available[j] == 0` | No division by zero (`eps`); clipped to [0, 1] |
| D3 | Resource with 0 total units | Blocked at construction |
| D4 | History shorter than 2 windows | `request_rate = 0` |
| D5 | Any indicator outside [0, 1] | Test fails |
| D6 | All resources free vs all exhausted | Matches hand-computed values |

#### E. Alarm logic (`test_warning.py`)

| # | Edge case | Expected / tested behaviour |
|---|---|---|
| E1 | Score hovers around threshold | Alarm only after `k` consecutive steps above threshold |
| E2 | **Score stays high for a long time** | One alarm per refractory period, not one per step |
| E3 | Risk score out of range | Always within 0 to 100 |

#### F. Evaluation (`test_events.py`, `test_metrics.py`), one hand-built test per row

| # | Edge case | Label |
|---|---|---|
| F1 | Alarm inside `[d - H_max, d - H_min]` of unsafe onset d | True alarm, event captured |
| F2 | **Alarm at the same step as unsafe onset (lead 0)** | Miss (detection, not prediction) |
| F3 | Alarm after onset, during the unsafe episode | Ignored for precision; event missed if no earlier valid alarm |
| F4 | Alarm with no unsafe onset in `(t, t + H_max]` | False alarm |
| F5 | Unsafe onset with no alarm in its valid window | Missed event |
| F6 | Several alarms before one event | First valid alarm gives lead time; others not counted as extra true alarms |
| F7 | One alarm before several events within H_max | Counts for the first event only |
| F8 | Long high-score stretch with no event | One false alarm per refractory period |
| F9 | **Alarm in the last H_max steps of a sequence** | Censored; excluded from precision |
| F10 | No alarms and no events | Counted as "quiet sequence"; no effect on precision/recall |
| F11 | Pairwise lead-time comparison | Only on events captured by both methods |

#### G. Experiment level (`experiments/`, integration checks)

| # | Edge case | Handling |
|---|---|---|
| G1 | Scenario never unsafe, or unsafe from step 1 | Caught by calibration (Phase 8); parameters tuned on tuning seeds |
| G2 | Tuning data leaking into test | Disjoint seed ranges (0 to 1,999 vs 100,000+); assert no overlap |
| G3 | Batch run crashes midway | Chunked output; resume by config hash |
| G4 | Detection too slow at large n | Scheduled detection: every step if n <= 50, else every c steps and whenever waiting set changes |
| G5 | Same config re-run | Skipped unless forced (idempotent runner) |

#### Highlight for the presentation / paper

These five show correctness thinking and should appear in the paper's method or threats section:

1. **A1:** safe never coexists with deadlock (property test)
2. **C3:** unsafe states can recover, so multiple episodes per sequence are handled
3. **F2:** lead time 0 counts as a miss, not a hit
4. **E2 / F8:** persistent alarms count once (refractory period)
5. **F9:** censored alarms at sequence end are excluded from precision

---

## 4. Tech Stack

| Purpose | Tool |
|---|---|
| Language | Python 3.11+ |
| Numerics | NumPy |
| Data | Pandas, PyArrow (Parquet) |
| Parallelism | `concurrent.futures.ProcessPoolExecutor` |
| Progress/logs | tqdm, logging |
| Config | YAML (PyYAML) |
| Tests | pytest, hypothesis (optional, property tests) |
| Plots | Matplotlib |
| System metrics | psutil |
| Server | AWS EC2 Ubuntu, tmux |
| Paper | LaTeX, IEEE conference template |

No frontend, no web server.

---

## 5. Folder Structure

```text
predictive-deadlock-warning/
├── README.md
├── IMPLEMENTATION_PLAN.md
├── requirements.txt
├── .gitignore                 # results/, *.parquet, .venv/
├── configs/
│   ├── smoke.yaml
│   ├── calibrate.yaml         # scenario class-balance check
│   ├── tuning.yaml
│   ├── main.yaml
│   └── scaling.yaml
├── pdw/
│   ├── __init__.py
│   ├── state.py
│   ├── banker.py              # safety (vectorised + reference), request check, detection
│   ├── scenarios.py
│   ├── indicators.py
│   ├── warning.py             # risk score, alarm onset logic, baselines
│   ├── simulator.py
│   ├── events.py              # unsafe/deadlock onset extraction, episodes
│   ├── metrics.py             # event-based precision/recall/lead time, bootstrap
│   └── io.py
├── experiments/
│   ├── run_batch.py
│   ├── calibrate.py
│   ├── tune.py
│   ├── evaluate.py            # applies tuned params to test results, all methods
│   └── scaling.py
├── analysis/
│   ├── make_tables.py
│   └── make_figures.py
├── tests/
│   ├── test_state.py
│   ├── test_banker.py
│   ├── test_scenarios.py
│   ├── test_indicators.py
│   ├── test_warning.py
│   ├── test_simulator.py
│   ├── test_events.py
│   └── test_metrics.py
├── deployment/EC2_SETUP.md
├── results/                   # gitignored
└── paper/
    ├── main.tex
    ├── refs.bib
    ├── figures/
    └── tables/
```

---

## 6. Phases

### Phase 1: State Model (`pdw/state.py`)
- `SystemState` with NumPy arrays: `total (m,)`, `available (m,)`, `max_claim (n,m)`, `allocation (n,m)`, `need` property, `waiting (n,) bool`, `pending (n,m)`, `finished (n,) bool`.
- `SystemState.random(n, m, rng, cfg)`: builds valid initial state; regenerates until SAFE (cap attempts, raise if impossible).
- `validate()`: non-negative arrays, `allocation <= max_claim`, conservation `available + allocation.sum(0) == total`, finished processes hold nothing.
- Tests: invariants for random n, m; deterministic by seed.

### Phase 2: Banker's and Detection (`pdw/banker.py`)
- `is_safe_reference(...)`: plain-loop textbook version.
- `is_safe(available, allocation, need, active)`: vectorised; each pass marks all active unfinished processes with `need <= work` row-wise, releases their allocation, repeats until no progress. Returns `(safe, order)`.
- `check_request(state, pid, req) -> GRANT | WAIT | EXCEEDS_NEED`.
- `is_deadlocked(state)`: detection algorithm using **pending requests** for waiting processes and zero request for running processes (optimistic assumption). Returns `(deadlocked, set_of_deadlocked_pids)`.
- Tests:
  - Silberschatz 5x3 textbook example: SAFE with a valid sequence.
  - Known unsafe example: UNSAFE.
  - Detection textbook example (7 A, 2 B, 6 C): not deadlocked; after P2 requests one more C: deadlocked.
  - Vectorised == reference on 2,000 random states.
  - Property: `deadlocked => not safe` on 2,000 random states.
- **Gate:** do not continue until all pass.

### Phase 3: Scenarios (`pdw/scenarios.py`)
- Interface: `generator(state, rng, cfg)` yields `(pid, request)` for the next step, choosing only among active, non-waiting processes. Returns `None` if no process can request.
- Implement `normal`, `spike`, `deadlock_prone` per Section 3.4. Parameters in config (request size range, burst length, burst size, preference probability, release probability).
- Tests: requests non-zero and `<= need`, only eligible processes chosen, deterministic by seed, spike window has larger mean request than baseline window.

### Phase 4: Simulator (`pdw/simulator.py`)
Step loop (observer mode):
```text
for t in range(steps):
    retry pending requests (FIFO): grant those that fit available
    draw (pid, req) from generator; if None and nothing pending -> end
    decision = check_request(...)  ->  GRANT allocate | WAIT mark waiting
    process completions (need == 0 -> release, finished)
    optional voluntary release (normal scenario)
    unsafe[t]      = not is_safe(...)
    deadlocked[t]  = is_deadlocked(...)  (per schedule in 3.9)
    indicators[t]  = compute_indicators(state, history)
    record compact per-step values (score inputs, unsafe, deadlocked)
    if deadlocked: end_reason = "deadlock"; break
```
- Returns: per-step arrays (indicators, unsafe, deadlocked, waiting count), end reason, runtime, time spent in Banker's.
- `validate()` after each step in debug mode.
- Tests: conservation every step, determinism, deadlock always implies unsafe on that step, sequences in `deadlock_prone` reach unsafe for some seeds.

### Phase 5: Indicators (`pdw/indicators.py`)
All in [0, 1], handle Section 3.6 edge cases:

| Indicator | Definition |
|---|---|
| `scarcity` | `1 - sum(available) / sum(total)` |
| `need_pressure` | mean over j of `clip(sum_active_need[j] / (available[j] + eps) / P, 0, 1)` where P is a fixed normaliser (e.g., n); document choice |
| `contention` | fraction of resource types j where >= 2 active processes have `need[i,j] > available[j]` |
| `waiting_ratio` | `waiting.sum() / max(1, active.sum())` |
| `request_rate` | `clip((units_requested_last_W - units_requested_prev_W) / (units_requested_prev_W + eps), 0, 1)` |

Tests: ranges, edge cases, hand-computed values on a small state.

### Phase 6: Warning Logic (`pdw/warning.py`)
- `risk_score(ind, w) = 100 * sum(w_i * ind_i) / sum(w_i)`.
- Levels for reporting: LOW 0 to 30, MEDIUM 31 to 60, HIGH 61 to 80, CRITICAL 81 to 100.
- `alarm_onsets(score, threshold, k, refractory)` returns list of alarm steps (Section 3.5).
- Methods (all computed offline from stored per-step indicators, so one simulation feeds all):
  `combined`, each single indicator, `baseline_availability`, `baseline_random`.
- Tests: onset logic with k and refractory on hand-made arrays.

### Phase 7: Events and Metrics (`pdw/events.py`, `pdw/metrics.py`)
- `onsets(bool_array)`, `episodes(bool_array)` (start, end, ended_in_deadlock).
- `evaluate_sequence(alarms, event_onsets, H_min, H_max, seq_len)` returns true/false alarms, captured/missed events, lead times, censored count (Section 3.5 table exactly).
- `aggregate(results)` and `bootstrap_ci(results, metric, B=1000)`.
- Tests: one hand-built case for every row of the Section 3.5 table.

### Phase 8: Calibration (`experiments/calibrate.py`)
- Run ~200 tuning seeds per scenario and size.
- Print per scenario: fraction of sequences with unsafe onset, mean number of unsafe episodes, fraction ending in deadlock, mean first-unsafe step.
- Adjust scenario parameters (tuning seeds only) until each scenario produces a meaningful mix. Freeze parameters in `configs/main.yaml`.

### Phase 9: Batch Runner (`experiments/run_batch.py`)
- `python -m experiments.run_batch --config configs/X.yaml`
- Expands grid (scenario x size x seed), runs in `ProcessPoolExecutor`, `workers: auto`.
- Per sequence, stores: compact per-step arrays needed to recompute all methods (indicators as float16/float32, unsafe, deadlocked, availability ratio) in chunked Parquet, plus a summary row.
- Resume by config hash. Writes `meta.json` (git commit, config, start/end, CPU count, RAM, instance type, library versions) and `run.log`.

Example `configs/main.yaml`:
```yaml
run_name: main_test
split: test
seeds: {start: 100000, count: 2000}
scenarios: [normal, spike, deadlock_prone]
sizes:
  - {processes: 10, resources: 5}
  - {processes: 25, resources: 8}
  - {processes: 50, resources: 10}
  - {processes: 100, resources: 20}
steps: 3000
indicator_window: 10
deadlock_check: {every_step_if_n_le: 50, else_every: 5}
store_full_trace_seeds: 5
workers: auto
```
`configs/smoke.yaml`: 2 scenarios, n=5, m=3, 20 seeds, 200 steps, under 1 minute locally.

### Phase 10: Tuning (`experiments/tune.py`)
- Uses tuning-split results only.
- For each method: grid over threshold (combined: 30 to 90 step 5; baselines: matching ranges), k in {1, 2, 3}, and for `combined` a small set of weight vectors (equal; each indicator doubled; each indicator removed).
- Objective: maximise F1 (alarm precision, event recall) with `H_max = 20`, subject to median lead >= 1. Record full PR curve too.
- Output `results/tuning/best_params.json`.

### Phase 11: Evaluation (`experiments/evaluate.py`)
- Applies frozen params to test-split results for all methods.
- Outputs: overall table, per-scenario table, per-size table, deadlock-target table, H_max sensitivity table, lead-time arrays for plots, PR curves (threshold sweep on test for plotting only, not selection).

### Phase 12: Scaling (`experiments/scaling.py`)
- n in {10, 25, 50, 100, 200}, m in {5, 10, 20}, 2,000 steps, 20 seeds.
- Measure: total time, time per safety check, time per detection check, steps/sec, peak RSS (psutil).
- Vectorised vs reference safety check timing for speed-up.
- Fit and report empirical growth vs the Θ(m·n²) expectation.

### Phase 13: EC2 Runs (`deployment/EC2_SETUP.md`)
1. Launch Ubuntu 24.04, compute-optimised 8 vCPU (e.g., c6i/c7i.2xlarge). Use free tier only for smoke tests. Set a billing alarm.
2. Security group: SSH (22) from your IP only.
3. Install: `python3-venv git tmux`; clone repo; create venv; `pip install -r requirements.txt`.
4. `pytest` must pass on the server.
5. In tmux: smoke, then calibrate, tuning, main, scaling. Detach with Ctrl+B D.
6. `scp -r` results back.
7. Stop or terminate the instance. No credentials in the repo.

### Phase 14: Analysis (`analysis/`)
Figures (PDF to `paper/figures/`):
1. Example timelines per scenario: risk score, threshold line, alarm onsets, shaded unsafe episodes, deadlock marker.
2. Lead-time distributions per method (captured events only).
3. Precision-recall curves per method, tuned operating points marked, random baseline.
4. Per-scenario F1 with 95% CI.
5. H_max sensitivity: precision/recall vs H_max.
6. Unsafe episode outcomes: recovered vs deadlocked, per scenario.
7. Scaling: time per safety check vs n (lines per m), log-log with fitted slope.
8. Vectorised vs reference speed-up.

Tables (LaTeX to `paper/tables/`): setup (sizes, seeds, total sequences, total steps/requests, instance type), main results, per scenario, deadlock target, ablation (remove one indicator), scaling.

### Phase 15: Paper (`paper/main.tex`, IEEE, 6 to 8 pages)
1. Abstract
2. Introduction
3. Background: Banker's (Dijkstra EWD108), safe vs unsafe vs deadlocked, cost Θ(mn²)
4. Related Work: improved Banker's variants (Kessels-style amortised O(mn); DBDAA 2024), ML-based deadlock prediction (INISCOM 2023, RL, AI-based), event-based early-warning evaluation
5. System Model: observer mode, request handling, lifecycle, targets
6. Early-Warning Algorithm: indicators, score, alarm onset, refractory period
7. Experimental Setup: scenarios, sizes, splits, EC2 hardware, totals
8. Results: RQ1 to RQ7
9. Discussion: circularity of need-based indicators, where alarms fail (spikes), practical value
10. Threats to Validity: synthetic workloads, fixed process set, known max claims, parameter choices
11. Conclusion and Future Work: learned models on same data, real traces, incremental safety checks, avoidance-mode variant

---

## 7. Timeline (Oct 1 to Oct 10)

| Date | Revanth | Sujju | Gate |
|---|---|---|---|
| Oct 1 | Phase 1, Phase 2 + tests | Repo, configs, Phase 3 scenarios | Banker's + detection tests pass |
| Oct 2 | Phase 5 indicators | Phase 4 simulator | One sequence runs end to end |
| Oct 3 | Phase 6 warning, Phase 7 events/metrics + tests | Phase 9 batch runner, smoke config | Smoke run passes locally |
| Oct 4 | Phase 8 calibration, freeze scenario params | EC2 setup, smoke run on EC2 | Calibrated scenarios |
| Oct 5 | Phase 10 tuning script | Launch tuning run on EC2 | Best params frozen |
| Oct 6 | Phase 11 evaluate script, Phase 12 scaling script | Launch main + scaling runs | Results downloaded |
| Oct 7 | Figures | Tables | All artifacts generated by scripts |
| Oct 8 | Paper: Model, Algorithm, Results | Paper: Intro, Background, Related Work, Setup | Full draft |
| Oct 9 | Discussion, Threats | Abstract, Conclusion, README | Final draft |
| Oct 10 | Review, submit, rehearse | Review, submit | Submitted |

Fallback if behind on Oct 5: drop n=100 size, reduce seeds to 1,000, drop deadlock-target figures (keep table).

---

## 8. Definition of Done

- [ ] All tests pass locally and on EC2, including `deadlocked => unsafe` property test
- [ ] Vectorised safety check matches reference
- [ ] Calibration shows each scenario produces a meaningful mix of unsafe/safe sequences
- [ ] Tuning used only tuning seeds; all reported numbers from test seeds
- [ ] Event-based metrics implemented exactly per Section 3.5, every case unit-tested
- [ ] Every row of the Edge Case Test Matrix (Section 3.10, A1 to G5) has a passing test or check
- [ ] Combined method compared with availability, random, and single-indicator baselines
- [ ] Both targets reported (unsafe onset, deadlock onset)
- [ ] 95% bootstrap CIs on headline metrics
- [ ] `meta.json` for every run; totals of sequences and steps reported
- [ ] Every number in the paper produced by a script
- [ ] EC2 instance stopped/terminated

---

## 9. Instructions for Claude Code

- Implement one phase at a time. Run `pytest` after each. Stop on failure.
- Pass `numpy.random.Generator` explicitly everywhere.
- Keep reference (slow) implementations for Banker's and detection for testing.
- Store per-step indicator arrays so all methods and thresholds can be evaluated offline without re-simulating.
- Never invent experimental numbers or hard-code a winner.
- Start with Phase 1 and Phase 2 using the Silberschatz 5x3 example and the 7A/2B/6C detection example.

---

## 10. References

1. E. W. Dijkstra, "Een algorithme ter voorkoming van de dodelijke omarming," EWD108, 1965. https://www.cs.utexas.edu/users/EWD/ewd01xx/EWD108.PDF
2. MIT Algorithm Wiki, "Banker's Algorithm (Deadlock Avoidance)." https://algorithm-wiki.csail.mit.edu/wiki/Banker%27s_Algorithm_(Deadlock_Avoidance_Deadlock_avoidance)
3. Modified banker's algorithm with amortised O(mn), BIT Numerical Mathematics. https://doi.org/10.1007/BF01933724
4. M. F. Zohora, F. Farhin, M. S. Kaiser, "DBDAA: A real-time approach to Dynamic Banker's Deadlock Avoidance Algorithm with optimized time complexity," PLOS ONE, 2024. https://doi.org/10.1371/journal.pone.0310807
5. A. Gottlieb, NYU Operating Systems lecture notes (safe/unsafe/deadlocked states). https://cs.nyu.edu/~gottlieb/courses/2000s/2004-05-spring/os202/lectures/lecture-13.html
6. H. Le Ngoc, H. Tran Cong, "Enhancing Load Balancing in Cloud Computing Through Deadlock Prediction," INISCOM 2023, Springer. https://doi.org/10.1007/978-3-031-47359-3_19
7. J. Oluwaseyi, "AI-Enhanced Predictive Systems for Thread Deadlock Resolution," EasyChair Preprint 14955, 2024.
8. S. L. Hyland et al., "Early prediction of circulatory failure in the intensive care unit using machine learning," Nature Medicine, 2020 (alarm precision / event recall).
9. J. Münchmeyer et al., "The transformer earthquake alerting model," arXiv:2009.06316 (warnings at/after onset counted as misses; warning time definition).
10. A. Silberschatz, P. B. Galvin, G. Gagne, *Operating System Concepts* (textbook examples for tests).
