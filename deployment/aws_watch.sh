#!/usr/bin/env bash
# Poll the runner until the pipeline finishes (or MAX_MIN minutes pass), printing
# progress. Exit 0 = pipeline finished OK, 1 = pipeline failed, 2 = still running,
# 3 = instance unreachable.
#   deployment/aws_watch.sh [MAX_MIN] [INTERVAL_S]
set -uo pipefail
cd "$(dirname "$0")/.."
source deployment/aws_common.sh
MAX_MIN=${1:-110}
INTERVAL=${2:-300}
end=$(( $(date +%s) + MAX_MIN * 60 ))
fails=0
while [ "$(date +%s)" -lt "$end" ]; do
    out=$(rsh 'cd pdw && grep -E "^== |PIPELINE" pipeline.log | tail -1; tail -1 pipeline.log; uptime | sed "s/.*load/load/"' 2>/dev/null)
    if [ -z "$out" ]; then
        fails=$((fails + 1)); echo "$(date +%H:%M) unreachable ($fails)"
        [ $fails -ge 3 ] && exit 3
    else
        fails=0; echo "$(date +%H:%M) | $(echo "$out" | tr '\n' ' | ')"
        if echo "$out" | grep -q "PIPELINE_EXIT=0"; then exit 0; fi
        if echo "$out" | grep -q "PIPELINE_EXIT="; then exit 1; fi
    fi
    sleep "$INTERVAL"
done
exit 2
