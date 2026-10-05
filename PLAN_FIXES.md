# Plan Fixes (v2 → v2.1)

Corrections to `OS_CASE_STUDY_FULL_CONTEXT.md` / `IMPLEMENTATION_PLAN.md`. Each fix states the problem, the exact replacement rule, and the test that enforces it. Where a fix conflicts with the original plan, this file wins.

---

## A. Evaluation semantics (`pdw/events.py`, `pdw/metrics.py`)

### A1. Censoring applies only to step-capped sequences (replaces §3.5 last row, F9)
**Problem:** "Alarm in last H_max steps is censored" treats every sequence as if its future were unknown. A sequence ending in deadlock or all-finished has a known future. An alarm in the tail that *is* followed by an onset is a true alarm and should not be discarded.
**Fix:** Every sequence gets `end_reason ∈ {max_steps, deadlock, all_finished}`. An alarm at step t is:
- **true**, if an event onset d satisfies `t ∈ [d - H_max, d - H_min]` (regardless of position in sequence);
- **censored** (excluded from precision), only if no onset follows in `(t, T-1]`, `end_reason == max_steps`, and `t > T-1 - H_max`;
- **false**, otherwise.
**Tests:** F9a: step-capped, alarm in tail, no onset → censored. F9b: step-capped, alarm in tail, onset follows → true. F9c: `ended_deadlock`/`all_finished`, alarm in tail, no further unsafe onset → false.

### A2. Episode outcomes get a third bucket (§3.5, RQ6)
**Problem:** Episodes are labelled only recovered/deadlocked. Episodes still running when the step cap is hit get misclassified.
**Fix:** `episode.outcome ∈ {recovered, deadlocked, censored}`. Report fractions over non-censored episodes, and report the censored count separately.
**Test:** Episode open at `T-1` with `end_reason == max_steps` → `censored`.

### A3. Alarms are suppressed while the system is already unsafe (refines §3.5 row 3, F3)
**Problem:** An alarm fired inside an unsafe episode is "ignored for precision" but still uses up the refractory period, so it can block a valid alarm for the next onset after recovery.
**Fix:** Before alarm logic, set `score_masked[t] = 0` wherever `unsafe[t]` is True. This means in-episode steps reset the k-counter and never start a refractory period. Banker's is already signalling there, so a warning adds nothing.
**Tests:** F3 updated: high score during an episode produces no alarm onset. A new alarm can fire `k` safe steps after recovery even if within R of an in-episode high score.

### A4. Flicker: minimum safe gap between events (new)
**Problem:** Observer mode can flip unsafe → safe → unsafe within 1–2 steps. Each re-onset becomes an event that is nearly impossible to "predict", which deflates recall artificially.
**Fix:** An unsafe onset at d is a **primary event** only if the previous `G` steps (`G = 5`, configurable) were all safe, or it is the first onset in the sequence. Re-onsets within G are merged into the preceding episode. Also report a second target, **first onset per sequence**, as a robustness check.
**Tests:** Pattern `S S U S U S S S S S S U` with G=5 → 2 events (onsets at 2 and 11), not 3.

### A5. Warm-up: events that cannot be caught are reported, not silently counted (new)
**Problem:** An onset at `d < k + H_min` cannot be captured by any method that needs k steps of score. `request_rate` is also 0 for the first `2W` steps.
**Fix:** Count events with `d < k_max + H_min` (k_max = 3) as `uncatchable_early`. Exclude them from recall for every method equally, and report their number. Calibration (C3) should make them rare.
**Test:** Onset at d=1 with k=2 → counted as `uncatchable_early`, not as a miss.

### A6. Undefined metrics (new)
**Fix:** If a method has 0 non-censored alarms, `alarm_precision = NaN` and the method's `F1 = 0` for tuning. If there are 0 events, `event_recall = NaN`. Aggregates use **micro-averaging** (sum counts over sequences, then divide), not a mean of per-sequence ratios.
**Test:** Aggregation over {seq with 0 alarms, seq with 1 true alarm} gives precision 1.0, not NaN.

### A7. Bootstrap is stratified (refines §3.5)
**Fix:** Resample sequences **within each (scenario, size) cell**, recompute micro-averaged metrics, B = 1,000, percentile 95% CI. Use a fixed bootstrap seed.

### A8. Refractory period is independent of H_max in the sensitivity study (§3.5, Phase 11)
**Problem:** With `R = H_max`, varying H_max in {5, 10, 20, 50} changes both the target window and the alarm generator, which confounds the sensitivity table.
**Fix:** R is a tuned/fixed parameter (default 20). The H_max sensitivity table re-evaluates **fixed alarm onsets** under different windows. Parameters are tuned once, at H_max = 20.

---

## B. Tuning and baselines (`pdw/warning.py`, `experiments/tune.py`)

### B1. Replace the vacuous tuning constraint (Phase 10)
**Problem:** "median lead ≥ 1" always holds, because H_min = 1 means every captured lead is ≥ 1.
**Fix:** Objective = maximise F1 subject to **`false_alarms_per_1000_steps ≤ FA_max`** (e.g., 5) and **median lead ≥ 3**. If no configuration meets the constraints, select max F1 and report that the constraint was infeasible. Record the full PR curve as before.

### B2. Random baseline uses the global matched rate (§3.7)
**Problem:** Matching combined's alarm count *per sequence* leaks which sequences are risky into the random baseline.
**Fix:** `p = total combined alarm onsets / total eligible (safe, non-refractory) steps`, computed on the **tuning split**. Random alarms are Bernoulli(p) on eligible steps, with the same refractory rule. Repeat with 10 random seeds per sequence and report the mean.

### B3. Add a strong state-based baseline: safety margin (§3.7, circularity threat)
**Problem:** Unsafe is a fixed function of `(available, allocation, need)`, the same state the indicators read. Beating "availability < t" proves little.
**Fix:** Add `baseline_lookahead`: at each safe step, `lookahead[t]` = fraction of active, non-waiting processes i for which granting `min(need[i], available)` would make the state unsafe. Alarm when `lookahead ≥ threshold` (tuned like the others).
- Cost is n safety checks per step, so compute it only for sizes with **n ≤ 25** (all seeds) and on a 200-seed subsample for larger n. Store it as an extra per-step column.
- Paper framing: *"combined vs lookahead"* is the honest comparison. Any outcome is reportable.

**Test:** Hand-built state where one grant flips safe → unsafe gives lookahead > 0.

### B4. Thresholds grids for baselines (Phase 10, made explicit)
- `availability`: `t_a ∈ {0.05, 0.10, …, 0.50}`
- single indicators and `combined`: threshold `30..90 step 5`
- `lookahead`: `{0.1, 0.2, …, 0.6}`
- all: `k ∈ {1, 2, 3}`, `R ∈ {10, 20}`

---

## C. Simulator and model (`pdw/simulator.py`, `pdw/banker.py`, `pdw/scenarios.py`, `pdw/state.py`)

### C1. Deadlock detection is event-driven and exact (replaces §3.9 row 2, G4, `deadlock_check` config)
**Problem:** "Every c steps for n > 50" is slower than necessary and delays deadlock onset by up to c−1 steps, which biases deadlock lead times.
**Argument:** Detection assumes every non-waiting process eventually releases everything it holds. A grant to or release by a non-waiting process only moves units between `available` and that process's allocation, and detection adds those units back anyway. So the detection outcome can change **only when the waiting set or a pending vector changes** (new WAIT, a pending request granted, or a process finishing).
**Fix:** Run `is_deadlocked` only on steps where `waiting` or `pending` changed. Otherwise copy the previous result. Remove `deadlock_check.every_step_if_n_le / else_every` from configs.
**Test:** On 500 random sequences, event-driven and every-step detection give identical `deadlocked` arrays.

### C2. Assert `pending ≤ need` (supports A1 of the test matrix)
**Problem:** `deadlocked ⇒ unsafe` holds only if every pending request is ≤ the process's remaining need.
**Fix:** `validate()` asserts `pending[i] ≤ need[i]` for all waiting i, and `pending[i] == 0` for non-waiting i.

### C3. Calibration knob: claim tightness (Phase 8, §3.4)
**Fix:** Define `tightness_j = sum_i max_claim[i,j] / total[j]` and make it the main generator parameter, sampled in a configured range per scenario. Calibration targets per scenario, on tuning seeds:
- 20–80% of sequences have ≥ 1 primary unsafe event (`normal` may sit at the low end, around 5–20%);
- median first-unsafe step > 2·H_max, so warning windows are not truncated;
- < 5% of events `uncatchable_early`.

Freeze the values in `configs/main.yaml`.

### C4. Per-sequence RNG from SeedSequence (§3.8)
**Fix:** `rng = np.random.default_rng(np.random.SeedSequence([seed, scenario_id, n, m]))`. Each (scenario, size) cell gets an independent stream. Tuning and test seed ranges stay disjoint.

### C5. Step semantics made explicit (Phase 4)
**Fix:** One step = one **new** request drawn from the generator.
- Pending retries at the start of the step are FIFO **by wait-start step**, and do not count as new requests for `request_rate`.
- Completions are processed after the grant, in the same step.
- If the generator returns `None` while pending requests exist, the state must be deadlocked: assert it, then end the sequence with `deadlock`.

**Test:** B7 with two waiters ordered by wait-start step.

### C6. Banker's equivalence test compares outcomes, not orders (A7 of the test matrix)
**Problem:** The vectorised pass returns a different (still valid) safe order from the reference loop.
**Fix:** The test asserts `safe_vec == safe_ref`. When the state is safe, it also asserts that the vectorised order is a valid safe sequence: replay it and check `need ≤ work` at every step. Finished processes are excluded from both.

### C7. Partial deadlock ends the sequence (clarifies C2 of the test matrix)
**Fix:** The sequence ends as soon as **any** non-empty deadlocked set exists, even if other processes could continue. Document this as a limitation: at most one deadlock onset per sequence.
**Convention (Silberschatz):** detection marks processes holding nothing as finished from the start, so a waiting process with zero allocation is never in the deadlocked set, even if it is blocked behind one. This does not change when sequences end (a deadlocked set always contains holders). State it in the paper's System Model. Tested by `test_waiting_process_holding_nothing_is_not_deadlocked`.

---

## D. Indicators (`pdw/indicators.py`)

### D1. `need_pressure` without the size-dependent normaliser (Phase 5)
**Problem:** `sum_need / (available + eps) / P` with `P = n` changes meaning across sizes, and needs eps plus clipping.
**Fix:** `need_pressure = mean_j  S_j / (S_j + available_j)` where `S_j = sum over active i of need[i,j]`. Define it as 0 when `S_j + available_j == 0`.
- Bounded in [0, 1] by construction, needs no eps, and is comparable across n and m.

**Test:** All free with no need → 0. available = 0 with need > 0 → 1.

### D2. `contention` normalised per resource (Phase 5, clarification)
**Fix:** Keep the definition (fraction of resource types where ≥ 2 active processes have `need[i,j] > available[j]`). State in the paper that it is a fraction of resource types, so it is size-comparable.

### D3. `request_rate` counts new requests only (Phase 5)
**Fix:** The windowed sum uses units of new requests (C5), excluding retries. It stays 0 until `2W` steps exist.

---

## E. Data, storage, runs (`experiments/run_batch.py`, configs)

### E1. Resolve the storage contradiction (§3.9 vs Phase 9 / §9)
**Fix:**
- **All sequences:** per-step `indicators (5 × float16)`, `lookahead (float16, when computed)`, `unsafe (bool)`, `deadlocked (bool)`, `avail_ratio (float16)`, `n_waiting (int16)`, plus a summary row containing `end_reason`.
- **5 seeds per cell:** full state traces (allocation/need/available) for figures.
- Estimate: about 18 bytes per step × 72M steps ≈ 1.3 GB raw per split. Parquet with zstd should give well under 1 GB. Chunk by (scenario, size, seed block).

### E2. Main-config defaults updated
```yaml
deadlock_check: event_driven        # replaces every_step_if_n_le / else_every
min_safe_gap: 5                     # A4
refractory: 20                      # A8 (independent of H_max)
lookahead: {max_n_all_seeds: 25, subsample_seeds: 200}   # B3
fa_max_per_1000: 5                  # B1
```

### E3. Scaling study timings (Phase 12)
**Fix:** Report detection time **per invocation** and **invocations per step** separately. With C1, detection runs only on waiting-set changes, so per-step cost depends on the scenario.

---

## F. Paper and admin

### F1. Threats-to-validity additions
These go in the paper's threats-to-validity section: circularity (B3), flicker merging (A4), partial deadlock ends the run (C7), uncatchable early events (A5), and synthetic claim tightness (C3).

### F2. Verify references before citing
Check refs 3 (BIT, DOI BF01933724: authorship and claim) and 7 (EasyChair 14955) against the actual sources. Cite only what each paper states.

### F3. Allotment record
Ask the faculty to update S.No 22 from "Memory Management Simulator" to the deadlock title.

### F4. Timeline reset (replaces §1.11 / §7; as of Oct 3 no code exists)
| Date | Work | Gate |
|---|---|---|
| Oct 3–4 | Phases 1–4 + tests | Textbook examples pass; one sequence runs end to end |
| Oct 5 | Phases 5–7, smoke, calibration (C3) | F-table tests pass, including the new F9a–c, A3–A6 tests |
| Oct 6 | Batch runner, EC2: tuning → main → scaling | Results downloaded, instance stopped |
| Oct 7 | Evaluate, figures, tables | Every artifact script-generated |
| Oct 8–9 | Paper | Final draft |
| Oct 10 | Submit, rehearse | — |

Fallback (unchanged trigger, applied earlier if needed): drop n=100, 1,000 seeds, deadlock figures → table only.

---

## Definition of Done additions
- [ ] Event-driven detection matches every-step detection (C1)
- [ ] Censoring, episode-outcome, suppression, flicker, warm-up tests pass (A1–A5)
- [ ] `lookahead` baseline reported alongside availability/random/single-indicator (B3)
- [ ] Tuning constraint is non-vacuous and its feasibility is reported (B1)
