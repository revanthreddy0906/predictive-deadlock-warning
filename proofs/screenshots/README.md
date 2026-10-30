# AWS CloudTrail records

CloudTrail is AWS's own log of account activity. These screenshots are from
CloudTrail > Event history, region ap-south-2 (Asia Pacific, Hyderabad). The console
shows event times in IST (UTC + 5 h 30 min); the event records use UTC.

| File | What it shows |
|---|---|
| `cloudtrail_runinstances.png` | Event name = RunInstances: the two server launches, 21 Oct 2026 11:11:48 IST and 8 Oct 2026 22:27:57 IST |
| `cloudtrail_runinstances_oct21_detail.png` | Event record of the main run's launch: `eventTime` 2026-10-21T05:41:48Z, `instanceType` c7i.8xlarge, 40 GB gp3 disk, key `pdw-key` |
| `cloudtrail_runinstances_oct08_detail.png` | Event record of the exploratory run's launch: `eventTime` 2026-10-08T16:57:57Z, `instanceType` c7i.8xlarge, 40 GB gp3 disk, key `pdw-key` |
| `cloudtrail_terminateinstances.png` | Event name = TerminateInstances: instance `i-0fc2fafad89770581` deleted 21 Oct 17:01:59 IST, instance `i-0f42079935bf28086` deleted 9 Oct 01:19:24 IST |

The client IP addresses in the two event records are masked.

## Extract of the event records

Taken from the full CloudTrail records; account number, access-key IDs, IP addresses
and network identifiers are omitted.

| Field | Main run | Exploratory run |
|---|---|---|
| `eventName` | RunInstances | RunInstances |
| `eventTime` (UTC) | 2026-10-21T05:41:48Z | 2026-10-08T16:57:57Z |
| `awsRegion` / availability zone | ap-south-2 / ap-south-2c | ap-south-2 / ap-south-2c |
| `instanceId` | i-0fc2fafad89770581 | i-0f42079935bf28086 |
| `instanceType` | c7i.8xlarge | c7i.8xlarge |
| `cpuOptions` | 16 cores x 2 threads = 32 vCPUs | 16 cores x 2 threads = 32 vCPUs |
| `architecture` | x86_64 | x86_64 |
| Disk | 40 GB gp3, deleted on termination | 40 GB gp3, deleted on termination |
| Tags | Project = pdw, Name = pdw-runner | Project = pdw, Name = pdw-runner |
| Security group | pdw-ssh | pdw-ssh |
| Launched with | AWS CLI (`ec2 run-instances`, from `deployment/aws_launch.sh`) | AWS CLI (`ec2 run-instances`) |
| Terminated (TerminateInstances, UTC) | 2026-10-21 11:31:59 | 2026-10-08 19:49:24 |
| Running time | 5 h 50 min (5.84 h) | 2 h 51 min (2.86 h) |
