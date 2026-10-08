# Running the experiments on AWS EC2

Budget: the full pipeline needs roughly 1 hour on an 8-vCPU instance (measured on an
8-core Mac first; see `results/*/meta.json`). On-demand c7i.2xlarge is about
$0.36-0.40/h, so the whole run should cost a few dollars. **The real risk is leaving the
instance running** (about $9/day). Terminate it the same day.

## 0. Before launching
- Billing -> Budgets: create a $15 cost budget with email alerts at 50% and 100%.
- Billing -> Credits: check the expiry date and which services the credits cover.

## 1. Launch
- AMI: Ubuntu Server 24.04 LTS (x86_64). Instance type: `c7i.2xlarge` (8 vCPU).
- Storage: 30 GB gp3.
- Key pair: create or select one; keep the `.pem` file private (`chmod 400`).
- Security group: inbound SSH (22) from **My IP** only. Nothing else.

## 2. Connect and set up
```bash
ssh -i ~/.ssh/YOUR_KEY.pem ubuntu@EC2_PUBLIC_IP
```
```bash
sudo apt-get update && sudo apt-get install -y python3-venv python3-pip git tmux
```
```bash
git clone https://github.com/YOUR_GITHUB_USERNAME/predictive-deadlock-warning.git && cd predictive-deadlock-warning
```
```bash
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
```
```bash
.venv/bin/python -m pytest
```
All tests must pass before continuing.

## 3. Run inside tmux
```bash
tmux new -s pdw
```
```bash
INSTANCE_TYPE=c7i.2xlarge ./run_all.sh 2>&1 | tee pipeline.log
```
Detach with `Ctrl+B` then `D`. Reattach later with `tmux attach -t pdw`. The batch runner
resumes from finished chunks if anything is interrupted.

## 4. Copy results back (run on your Mac)
```bash
scp -i ~/.ssh/YOUR_KEY.pem -r ubuntu@EC2_PUBLIC_IP:~/predictive-deadlock-warning/results ./results_ec2
```
```bash
scp -i ~/.ssh/YOUR_KEY.pem -r ubuntu@EC2_PUBLIC_IP:~/predictive-deadlock-warning/paper ./paper_ec2
```

## 5. Terminate
EC2 console -> Instances -> select -> Instance state -> **Terminate** (not just Stop:
a stopped instance still bills for its disk). Confirm the volume is deleted.

No AWS credentials or keys ever go into the repository.
