#!/usr/bin/env bash
# Send N requests through the ingress and count which version/track answered.
# Usage: ./traffic-check.sh <host> [requests] [extra curl args]
#   ./traffic-check.sh canary.aceest.local 100
#   ./traffic-check.sh ab.aceest.local 20 -H "X-Variant: B"
#   ./traffic-check.sh ab.aceest.local 20 --cookie ab_variant=always
# INGRESS_IP defaults to $(minikube ip).
set -euo pipefail
HOST="${1:?usage: traffic-check.sh <host> [requests] [curl args]}"; N="${2:-50}"; shift $(( $# >= 2 ? 2 : 1 ))
IP="${INGRESS_IP:-$(minikube ip)}"
for _ in $(seq 1 "$N"); do
  curl -s -o /dev/null -D - -H "Host: $HOST" "$@" "http://$IP/api/version" \
    | awk -F': ' 'tolower($1)=="x-app-version"{v=$2} tolower($1)=="x-deployment-track"{t=$2} END{gsub("\r","",v); gsub("\r","",t); print "v" v " (" t ")"}'
done | sort | uniq -c | sort -rn
