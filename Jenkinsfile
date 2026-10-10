// ---------------------------------------------------------------------------
// ACEest Fitness & Gym - Jenkins BUILD & Quality Gate
// Pulls the latest code from GitHub, performs a clean build in a fresh
// virtualenv, lints, runs Pytest, then builds and verifies the Docker image.
// Requirements on the agent: python3 (+ venv), docker CLI with daemon access.
// ---------------------------------------------------------------------------
pipeline {
    agent any

    options {
        buildDiscarder(logRotator(numToKeepStr: '15'))
        disableConcurrentBuilds()
        timeout(time: 20, unit: 'MINUTES')
    }

    // Poll GitHub every ~5 minutes; a GitHub webhook (/github-webhook/) makes it instant.
    triggers {
        pollSCM('H/5 * * * *')
    }

    environment {
        IMAGE_NAME = 'aceest-fitness'
        IMAGE_TAG  = "${env.BUILD_NUMBER}"
        VENV       = "${WORKSPACE}/.venv"
    }

    stages {
        stage('Checkout') {
            steps {
                checkout scm
                sh 'git log -1 --pretty="format:%h %an: %s"'
            }
        }

        stage('Clean Build Environment') {
            steps {
                sh '''
                    rm -rf "$VENV" reports
                    python3 -m venv "$VENV"
                    . "$VENV/bin/activate"
                    pip install --upgrade pip
                    pip install -r requirements-dev.txt
                    python -m compileall -q app.py aceest tests
                '''
            }
        }

        stage('Lint') {
            steps {
                sh '. "$VENV/bin/activate" && flake8 app.py aceest tests --statistics'
            }
        }

        stage('Unit Tests') {
            steps {
                sh '''
                    . "$VENV/bin/activate"
                    mkdir -p reports
                    pytest -v --junitxml=reports/junit.xml \
                           --cov=app --cov=aceest \
                           --cov-report=xml:reports/coverage.xml \
                           --cov-fail-under=90
                '''
            }
        }

        stage('Docker Build') {
            steps {
                sh '''
                    docker build --target test -t $IMAGE_NAME:test .
                    docker build --target runtime -t $IMAGE_NAME:$IMAGE_TAG -t $IMAGE_NAME:latest .
                '''
            }
        }

        stage('Container Tests') {
            steps {
                sh 'docker run --rm $IMAGE_NAME:test pytest -q'
                sh '''
                    docker rm -f aceest-ci-$BUILD_NUMBER 2>/dev/null || true
                    docker run -d --name aceest-ci-$BUILD_NUMBER $IMAGE_NAME:$IMAGE_TAG
                    for i in $(seq 1 20); do
                        docker exec aceest-ci-$BUILD_NUMBER python -c \
                          "import urllib.request; urllib.request.urlopen('http://127.0.0.1:5000/health')" \
                          && break
                        sleep 1
                    done
                    docker exec aceest-ci-$BUILD_NUMBER python -c \
                      "import urllib.request; print(urllib.request.urlopen('http://127.0.0.1:5000/health').read().decode())"
                '''
            }
            post {
                always {
                    sh 'docker rm -f aceest-ci-$BUILD_NUMBER 2>/dev/null || true'
                }
            }
        }
    }

    post {
        always {
            junit allowEmptyResults: true, testResults: 'reports/junit.xml'
            archiveArtifacts artifacts: 'reports/*.xml', allowEmptyArchive: true
        }
        success {
            echo "BUILD OK - image ${IMAGE_NAME}:${IMAGE_TAG} is ready"
        }
        failure {
            echo 'BUILD FAILED - check the stage logs above'
        }
    }
}
