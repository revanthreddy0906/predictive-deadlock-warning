#!/usr/bin/env bash
# Launch exactly one tagged runner instance with every cost guard in place.
#   deployment/aws_launch.sh
# Guards: refuses if a pdw instance already exists; shutdown behaviour = stop;
# 10-hour OS timer (user data); idle-CPU alarm -> stop; root volume deleted on
# terminate; SSH only from this machine's public IP; IMDSv2.
set -euo pipefail
cd "$(dirname "$0")/.."
source deployment/aws_common.sh

echo "== checks"
aws ec2 describe-instance-type-offerings $A --location-type region \
    --filters Name=instance-type,Values="$TYPE" --query 'InstanceTypeOfferings[0].InstanceType' --output text | grep -qx "$TYPE"
existing=$(aws ec2 describe-instances $A --filters Name=tag:Project,Values=pdw \
    Name=instance-state-name,Values=pending,running,stopping,stopped \
    --query 'Reservations[].Instances[].InstanceId' --output text)
[ -z "$existing" ] || { echo "a pdw instance already exists: $existing"; exit 1; }
AMI=$(aws ec2 describe-images $A --owners 099720109477 \
    --filters 'Name=name,Values=ubuntu/images/hvm-ssd-gp3/ubuntu-noble-24.04-amd64-server-*' Name=state,Values=available \
    --query 'sort_by(Images,&CreationDate)[-1].ImageId' --output text)
VPC=$(aws ec2 describe-vpcs $A --filters Name=isDefault,Values=true --query 'Vpcs[0].VpcId' --output text)
MYIP=$(curl -s https://checkip.amazonaws.com)
echo "type=$TYPE ami=$AMI vpc=$VPC my_ip=$MYIP"

echo "== key pair"
if [ ! -f "$KEY" ]; then
    aws ec2 create-key-pair $A --key-name pdw-key --key-type ed25519 \
        --tag-specifications 'ResourceType=key-pair,Tags=[{Key=Project,Value=pdw}]' \
        --query KeyMaterial --output text > "$KEY"
    chmod 400 "$KEY"
fi

echo "== security group"
SG=$(aws ec2 describe-security-groups $A --filters Name=group-name,Values=pdw-ssh Name=vpc-id,Values="$VPC" \
    --query 'SecurityGroups[0].GroupId' --output text)
if [ "$SG" = "None" ]; then
    SG=$(aws ec2 create-security-group $A --group-name pdw-ssh --description "pdw: SSH from one IP" --vpc-id "$VPC" \
        --tag-specifications 'ResourceType=security-group,Tags=[{Key=Project,Value=pdw}]' --query GroupId --output text)
    aws ec2 authorize-security-group-ingress $A --group-id "$SG" --protocol tcp --port 22 --cidr "$MYIP/32" >/dev/null
fi
echo "$SG" > "$STATE/sg_id"

echo "== launch $TYPE"
IID=$(aws ec2 run-instances $A --image-id "$AMI" --instance-type "$TYPE" --count 1 \
    --key-name pdw-key --security-group-ids "$SG" \
    --instance-initiated-shutdown-behavior stop \
    --block-device-mappings '[{"DeviceName":"/dev/sda1","Ebs":{"VolumeSize":40,"VolumeType":"gp3","DeleteOnTermination":true}}]' \
    --metadata-options HttpTokens=required \
    --user-data file://deployment/user_data.sh \
    --tag-specifications 'ResourceType=instance,Tags=[{Key=Project,Value=pdw},{Key=Name,Value=pdw-runner}]' \
                         'ResourceType=volume,Tags=[{Key=Project,Value=pdw}]' \
    --query 'Instances[0].InstanceId' --output text)
echo "$IID" > "$STATE/instance_id"
date -u +%FT%TZ > "$STATE/launched_at"
aws ec2 wait instance-running $A --instance-ids "$IID"
aws ec2 describe-instances $A --instance-ids "$IID" --query 'Reservations[0].Instances[0].PublicIpAddress' --output text > "$STATE/ip"
echo "instance=$IID ip=$(ip)"

echo "== idle alarm (avg CPU < 2% for 30 min -> stop)"
aws cloudwatch put-metric-alarm $A --alarm-name pdw-idle-stop \
    --namespace AWS/EC2 --metric-name CPUUtilization --dimensions Name=InstanceId,Value="$IID" \
    --statistic Average --period 300 --evaluation-periods 6 --threshold 2 \
    --comparison-operator LessThanThreshold --treat-missing-data notBreaching \
    --alarm-actions "arn:aws:automate:$REGION:ec2:stop" \
    || echo "WARNING: idle alarm NOT created (the 10-hour timer still caps cost)"
echo "launched OK"
