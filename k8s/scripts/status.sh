#!/usr/bin/env bash
# Show what every strategy is running and where to reach it.
source "$(dirname "$0")/common.sh"
k get deployments -o custom-columns='DEPLOYMENT:.metadata.name,STRATEGY:.metadata.labels.strategy,TRACK:.metadata.labels.track,IMAGE:.spec.template.spec.containers[0].image,READY:.status.readyReplicas,WANTED:.spec.replicas'
echo
k get ingress -o custom-columns='INGRESS:.metadata.name,HOST:.spec.rules[0].host,SERVICE:.spec.rules[0].http.paths[0].backend.service.name,CANARY-WEIGHT:.metadata.annotations.nginx\.ingress\.kubernetes\.io/canary-weight'
echo
"$(dirname "$0")/blue-green.sh" status
