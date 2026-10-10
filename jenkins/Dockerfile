# Jenkins controller with Python 3 and the Docker CLI, so the Jenkinsfile
# stages (venv, pytest, docker build) can run on the built-in agent.
FROM jenkins/jenkins:lts-jdk17
USER root
RUN apt-get update \
 && apt-get install -y --no-install-recommends python3 python3-venv python3-pip docker.io git \
 && rm -rf /var/lib/apt/lists/*
USER jenkins
