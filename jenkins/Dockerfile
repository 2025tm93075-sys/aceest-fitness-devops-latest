# Jenkins controller able to run the whole ACEest pipeline on its built-in
# agent: Python 3 (venv + pytest), Docker CLI (build/push), kubectl (deploy).
FROM jenkins/jenkins:lts-jdk17
USER root
# Lab image: apt packages follow the base image release, so they are not pinned.
ARG KUBECTL_VERSION=v1.30.6
# hadolint ignore=DL3008
RUN apt-get update \
 && apt-get install -y --no-install-recommends python3 python3-venv python3-pip docker.io git curl \
 && rm -rf /var/lib/apt/lists/* \
 && curl -fsSLo /usr/local/bin/kubectl "https://dl.k8s.io/release/${KUBECTL_VERSION}/bin/linux/amd64/kubectl" \
 && chmod +x /usr/local/bin/kubectl
USER jenkins
COPY --chown=jenkins:jenkins plugins.txt /usr/share/jenkins/ref/plugins.txt
RUN jenkins-plugin-cli --plugin-file /usr/share/jenkins/ref/plugins.txt
