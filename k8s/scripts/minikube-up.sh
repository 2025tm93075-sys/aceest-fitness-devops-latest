#!/usr/bin/env bash
# Start a local Minikube cluster with the NGINX ingress controller and print
# the hosts entries needed to reach every strategy.
set -euo pipefail
minikube status >/dev/null 2>&1 || minikube start --cpus=4 --memory=6g --driver="${MINIKUBE_DRIVER:-docker}"
minikube addons enable ingress
minikube addons enable metrics-server || true
kubectl -n ingress-nginx rollout status deployment/ingress-nginx-controller --timeout=180s
IP="$(minikube ip)"
cat <<HOSTS

Add this line to /etc/hosts (Windows: C:\\Windows\\System32\\drivers\\etc\\hosts):

$IP rolling.aceest.local bluegreen.aceest.local canary.aceest.local ab.aceest.local shadow.aceest.local

NodePorts: rolling http://$IP:30080  blue-green live http://$IP:30081  preview http://$IP:30082
(With the docker driver on macOS/Windows run 'minikube tunnel' and use 127.0.0.1 instead.)
HOSTS
