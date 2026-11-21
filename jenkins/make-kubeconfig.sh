#!/usr/bin/env bash
# Produce a self-contained kubeconfig that the Jenkins container can use to
# reach Minikube over the shared "minikube" Docker network. Upload the file
# to Jenkins as a "Secret file" credential with ID: minikube-kubeconfig
set -euo pipefail
OUT="${1:-jenkins/kubeconfig-minikube.yaml}"
kubectl config view --minify --flatten --context=minikube \
  | sed "s#server: https://.*#server: https://$(minikube ip):8443#" > "$OUT"
chmod 600 "$OUT"
echo "Wrote $OUT (do NOT commit it). Server: https://$(minikube ip):8443"
