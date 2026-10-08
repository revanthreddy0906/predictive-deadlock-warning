#!/usr/bin/env bash
# Read-only check that nothing billable is left in ap-south-2. Exit 0 only if clean.
set -uo pipefail
cd "$(dirname "$0")/.."
source deployment/aws_common.sh
bad=0
check() {  # name, value
    if [ -n "$2" ] && [ "$2" != "None" ]; then echo "LEFT: $1 -> $2"; bad=1; else echo "ok: no $1"; fi
}
check "live instances" "$(aws ec2 describe-instances $A --filters Name=instance-state-name,Values=pending,running,stopping,stopped \
    --query 'Reservations[].Instances[].[InstanceId,InstanceType,State.Name]' --output text)"
check "volumes" "$(aws ec2 describe-volumes $A --query 'Volumes[].[VolumeId,State]' --output text)"
check "elastic IPs" "$(aws ec2 describe-addresses $A --query 'Addresses[].PublicIp' --output text)"
check "snapshots" "$(aws ec2 describe-snapshots $A --owner-ids self --query 'Snapshots[].SnapshotId' --output text)"
check "pdw security group" "$(aws ec2 describe-security-groups $A --filters Name=group-name,Values=pdw-ssh --query 'SecurityGroups[].GroupId' --output text)"
check "pdw alarm" "$(aws cloudwatch describe-alarms $A --alarm-names pdw-idle-stop --query 'MetricAlarms[].AlarmName' --output text)"
[ $bad -eq 0 ] && echo "AUDIT CLEAN" || echo "AUDIT FOUND LEFTOVERS"
exit $bad
