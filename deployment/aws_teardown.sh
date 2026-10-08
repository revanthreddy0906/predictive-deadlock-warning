#!/usr/bin/env bash
# Terminate the runner and delete everything tagged/created for it, then audit.
#   deployment/aws_teardown.sh
set -uo pipefail
cd "$(dirname "$0")/.."
source deployment/aws_common.sh

ids=$(aws ec2 describe-instances $A --filters Name=tag:Project,Values=pdw \
    Name=instance-state-name,Values=pending,running,stopping,stopped \
    --query 'Reservations[].Instances[].InstanceId' --output text)
if [ -n "$ids" ]; then
    echo "== terminate $ids"
    aws ec2 terminate-instances $A --instance-ids $ids >/dev/null
    aws ec2 wait instance-terminated $A --instance-ids $ids
fi
echo "== alarm";          aws cloudwatch delete-alarms $A --alarm-names pdw-idle-stop
echo "== security group"
sg=$(aws ec2 describe-security-groups $A --filters Name=group-name,Values=pdw-ssh --query 'SecurityGroups[0].GroupId' --output text)
[ "$sg" = "None" ] || aws ec2 delete-security-group $A --group-id "$sg"
echo "== key pair";       aws ec2 delete-key-pair $A --key-name pdw-key >/dev/null; rm -f "$KEY"
deployment/aws_audit.sh
