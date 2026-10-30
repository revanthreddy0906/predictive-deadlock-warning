# Proof of the cloud runs

All experiments ran on Amazon Web Services (AWS) EC2 in the Asia Pacific (Hyderabad)
region, `ap-south-2`. Each server was deleted after its run, so neither appears as a
running instance. The evidence is the logs and records the servers wrote during the runs
(in this repository) and AWS's own CloudTrail records (`screenshots/`).

All times are UTC. India time (IST) = UTC + 5 h 30 min.

## Summary

| | Main run (reported in the paper) | Exploratory run |
|---|---|---|
| Date | 21 Oct 2026 | 8 Oct 2026 |
| Server | c7i.8xlarge: 32 vCPUs, 61 GB RAM, Ubuntu 24.04 | c7i.8xlarge: 32 vCPUs, 61 GB RAM, Ubuntu 24.04 |
| Launched | 05:41 UTC (11:11 IST) | 16:57 UTC (22:27 IST) |
| Tuning simulation | 05:50-06:59 UTC, 45,000 sequences | 17:06-18:06 UTC, 150,000 sequences |
| Test simulation | 06:59-10:19 UTC, 150,000 sequences, 338,262,425 steps | 18:06-19:05 UTC, 150,000 sequences, 338,262,425 steps |
| Terminated | 11:31 UTC (17:01 IST) | 19:49 UTC (01:19 IST, 9 Oct) |
| Instance hours | 5.84 | 2.86 |
| Estimated cost | about US$8.39 | about US$4.11 |
| Instance ID | `i-0fc2fafad89770581` | `i-0f42079935bf28086` |

Both runs were paid from AWS credits; the total was about US$12.50. The CloudTrail
records match these times: `RunInstances` at 05:41:48 and 16:57:57 UTC,
`TerminateInstances` at 11:31:59 and 19:49:24 UTC.

## Where the evidence is

| Evidence | Main run | Exploratory run |
|---|---|---|
| Full pipeline log (tests, smoke, calibration, simulations, tuning, evaluation, figures; ends `PIPELINE_EXIT=0`) | [`data/pipeline_main_run.log`](../data/pipeline_main_run.log) | [`exploratory_run_oct08/pipeline.log`](exploratory_run_oct08/pipeline.log) |
| Timestamped simulation progress (32 workers) | [`data/c_main/run.log`](../data/c_main/run.log), [`data/c_tuning_small/run.log`](../data/c_tuning_small/run.log) | [`exploratory_run_oct08/simulation_test/run.log`](exploratory_run_oct08/simulation_test/run.log), [`simulation_tuning/run.log`](exploratory_run_oct08/simulation_tuning/run.log) |
| Machine details recorded by the server itself (`"instance_type": "c7i.8xlarge"`, `"cpu_count": 32`, `"ram_gb": 61.8`, Linux AWS kernel, start and finish times, git commit) | [`data/c_main/meta.json`](../data/c_main/meta.json), [`data/c_tuning_small/meta.json`](../data/c_tuning_small/meta.json) | [`exploratory_run_oct08/simulation_test/meta.json`](exploratory_run_oct08/simulation_test/meta.json), [`simulation_tuning/meta.json`](exploratory_run_oct08/simulation_tuning/meta.json) |
| Results produced on the server | [`data/c_main/eval/`](../data/c_main/eval) | [`exploratory_run_oct08/eval/`](exploratory_run_oct08/eval) |
| Run record: launch and termination times, hours, cost breakdown, cost guards, clean-up audit | [`deployment/aws_run.json`](../deployment/aws_run.json) | [`deployment/aws_run_b.json`](../deployment/aws_run_b.json) |
| AWS instance ID | [`main_run_instance_id.txt`](main_run_instance_id.txt) | |
| AWS CloudTrail launch and termination records | [`screenshots/`](screenshots/README.md) | [`screenshots/`](screenshots/README.md) |

The scripts used to launch, watch, delete and audit the servers are in
[`deployment/`](../deployment).

## Notes

- The `RuntimeWarning: divide by zero` lines in the main run's pipeline log come from a
  bug found during the run. It was fixed and the affected steps (tuning, evaluation,
  figures) were re-run before any result was reported, as the paper describes
  (Section IV-C, "Deviations and post-hoc choices").
- The main run's pipeline took 5 h 40 min, including a 42-minute stall caused by too many
  threads per worker; it was fixed and resumed.
- Costs are estimates from instance hours at US$1.428/hour plus disk and IP charges; the
  exact amounts are in the AWS Billing console.
- Only the main run's results are reported in the paper. The exploratory run used fewer
  methods and is never pooled with it.
