#!/usr/bin/env bash
# Prints how many agents this goal may run at once (the skill dispatches up to these):
#   limit      — agents that edit and build: min(cores/2 (halved if busy), free RAM GB / 1.5, 8, ready)
#                minus steps other goals are running
#   read_limit — read-only agents (research, review, test design; no local load): min(8, ready)
# Usage: resources.sh <ready_steps> [store_dir] [own_slug]
ready=${1:-5}
store=${2:-}
own=${3:-}
cores=$(nproc)
free_gb=$(awk '/MemAvailable/ {printf "%.1f", $2/1048576}' /proc/meminfo)
load=$(cut -d' ' -f1 /proc/loadavg)
by_cpu=$(( cores / 2 )); [ "$by_cpu" -lt 1 ] && by_cpu=1
busy=$(awk -v l="$load" -v c="$cores" 'BEGIN {print (l > c*0.7) ? 1 : 0}')
[ "$busy" -eq 1 ] && by_cpu=$(( by_cpu / 2 > 0 ? by_cpu / 2 : 1 ))
by_ram=$(awk -v f="$free_gb" 'BEGIN {n=int(f/1.5); print (n<1?1:n)}')

others=0
if [ -n "$store" ] && [ -d "$store" ]; then
  for plan in "$store"/*/plan.md; do
    [ -f "$plan" ] || continue
    slug=$(basename "$(dirname "$plan")")
    [ "$slug" = "$own" ] && continue
    grep -q '^goal: .*status: \(running\)' "$plan" || continue
    n=$(grep -cE '^\| S[0-9]+ .*\| (running|testing|fixing) \|' "$plan")
    others=$(( others + n ))
  done
fi

CAP=8
limit=$(printf '%s\n' "$by_cpu" "$by_ram" "$CAP" "$ready" | sort -n | head -1)
limit=$(( limit - others )); [ "$limit" -lt 1 ] && limit=1
read_limit=$(printf '%s\n' "$CAP" "$ready" | sort -n | head -1); [ "$read_limit" -lt 1 ] && read_limit=1
echo "limit=$limit read_limit=$read_limit cores=$cores free_ram_gb=$free_gb load=$load other_goals_running_steps=$others"
