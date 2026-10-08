# Shared settings for the deployment scripts (sourced, not executed).
PROFILE=${PDW_AWS_PROFILE:-pdw}
REGION=ap-south-2
TYPE=${PDW_INSTANCE_TYPE:-c7i.8xlarge}
A="--profile $PROFILE --region $REGION"
STATE=deployment/.state
KEY="$HOME/.ssh/pdw-key.pem"
mkdir -p "$STATE"
SSH_OPTS=(-i "$KEY" -o StrictHostKeyChecking=accept-new -o UserKnownHostsFile="$STATE/known_hosts"
          -o ConnectTimeout=15 -o ServerAliveInterval=30)
ip()  { cat "$STATE/ip"; }
iid() { cat "$STATE/instance_id"; }
rsh() { ssh "${SSH_OPTS[@]}" "ubuntu@$(ip)" "$@"; }
