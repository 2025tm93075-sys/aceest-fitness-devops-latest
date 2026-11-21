// ---------------------------------------------------------------------------
// ACEest Fitness & Gym - Jenkins CI/CD pipeline (Assignment 2)
//
//   Checkout -> Build & Unit Tests -> SonarQube Analysis -> Quality Gate
//   -> Docker Build -> Tests in Containers -> Push to Docker Hub
//   -> Build Artifacts -> Deploy to Kubernetes (strategy) -> automatic rollback
//
// Jenkins setup (one time) is described in README.md, section "Jenkins".
// Credentials used:  dockerhub-creds (username/password or access token)
//                    minikube-kubeconfig (secret file)
// Tools used:        SonarQube server "SonarQube", scanner tool "SonarScanner"
// ---------------------------------------------------------------------------
pipeline {
    agent any

    options {
        buildDiscarder(logRotator(numToKeepStr: '20', artifactNumToKeepStr: '10'))
        disableConcurrentBuilds()
        timeout(time: 45, unit: 'MINUTES')
        timestamps()
        ansiColor('xterm')
    }

    // Poll GitHub every 2 minutes; a GitHub webhook triggers builds instantly.
    triggers {
        pollSCM('H/2 * * * *')
        githubPush()
    }

    parameters {
        choice(name: 'DEPLOY_STRATEGY',
               choices: ['rolling', 'blue-green', 'canary', 'ab-test', 'shadow', 'all', 'none'],
               description: 'Deployment strategy for this build (polled builds use the first choice)')
        string(name: 'CANARY_WEIGHT', defaultValue: '20', description: 'Percent of traffic sent to the canary')
        booleanParam(name: 'PROMOTE', defaultValue: true,
                     description: 'Promote canary / shadow to 100% after their checks pass')
        booleanParam(name: 'SIMULATE_FAILURE', defaultValue: false,
                     description: 'Rollback drill: deploy a release with failing health checks (rolling strategy)')
        booleanParam(name: 'PUSH_IMAGES', defaultValue: true, description: 'Push images to Docker Hub')
    }

    environment {
        // >>> Change this to your Docker Hub username (the only edit needed) <<<
        DOCKERHUB_USER = 'your-dockerhub-username'
        IMAGE_REPO     = "docker.io/${DOCKERHUB_USER}/aceest-fitness"
        TEST_REPO      = "docker.io/${DOCKERHUB_USER}/aceest-fitness-test"
        STABLE_TAG     = 'v1.1.0'            // baseline used when the cluster is bootstrapped
        VENV           = "${WORKSPACE}/.venv"
    }

    stages {
        stage('Checkout') {
            steps {
                checkout scm
                script {
                    env.APP_VERSION = sh(returnStdout: true,
                        script: 'python3 -c "import aceest; print(aceest.__version__)"').trim()
                    env.GIT_SHA   = sh(returnStdout: true, script: 'git rev-parse --short HEAD').trim()
                    env.IMAGE_TAG = "v${env.APP_VERSION}"
                    env.BUILD_TAG_FULL = "v${env.APP_VERSION}-b${env.BUILD_NUMBER}"
                    currentBuild.displayName = "#${env.BUILD_NUMBER} ${env.IMAGE_TAG} (${env.GIT_SHA})"
                    if (env.DOCKERHUB_USER == 'your-dockerhub-username') {
                        error 'Set DOCKERHUB_USER in the Jenkinsfile environment block'
                    }
                }
                sh 'git log -1 --pretty="format:%h %an: %s%n"'
            }
        }

        stage('Build & Unit Tests') {
            steps {
                sh '''
                    rm -rf "$VENV" reports dist
                    mkdir -p reports dist
                    python3 -m venv "$VENV"
                    . "$VENV/bin/activate"
                    pip install --quiet --upgrade pip
                    pip install --quiet -r requirements-dev.txt
                    python -m compileall -q app.py ACEest_Fitness.py aceest tests
                    flake8 app.py ACEest_Fitness.py aceest tests --tee --output-file=reports/flake8.txt
                    pytest -v --junitxml=reports/junit.xml \
                           --cov=app --cov=aceest \
                           --cov-report=xml:reports/coverage.xml --cov-report=term \
                           --cov-fail-under=90
                '''
            }
        }

        stage('SonarQube Analysis') {
            steps {
                script {
                    def scanner = tool 'SonarScanner'
                    withSonarQubeEnv('SonarQube') {
                        sh """
                            ${scanner}/bin/sonar-scanner \
                              -Dsonar.projectVersion=${env.APP_VERSION} \
                              -Dsonar.scm.revision=\$(git rev-parse HEAD)
                        """
                    }
                }
            }
        }

        stage('Quality Gate') {
            steps {
                // SonarQube calls back http://<jenkins>/sonarqube-webhook/ when analysis is done
                timeout(time: 10, unit: 'MINUTES') {
                    waitForQualityGate abortPipeline: true
                }
            }
        }

        stage('Docker Build') {
            steps {
                sh '''
                    docker build --target runtime \
                      --build-arg APP_VERSION="$APP_VERSION" \
                      --build-arg VCS_REF="$(git rev-parse HEAD)" \
                      --build-arg BUILD_DATE="$(date -u +%Y-%m-%dT%H:%M:%SZ)" \
                      -t "$IMAGE_REPO:$IMAGE_TAG" -t "$IMAGE_REPO:$BUILD_TAG_FULL" -t "$IMAGE_REPO:latest" .
                    docker build --target test \
                      -t "$TEST_REPO:$IMAGE_TAG" -t "$TEST_REPO:latest" .
                    docker image ls "$IMAGE_REPO"
                '''
            }
        }

        stage('Tests in Containers') {
            steps {
                sh '''
                    NET="aceest-ci-$BUILD_NUMBER"
                    docker network create "$NET" >/dev/null
                    trap 'docker rm -f "aceest-app-$BUILD_NUMBER" >/dev/null 2>&1; docker network rm "$NET" >/dev/null 2>&1' EXIT

                    echo "== Unit tests inside the test image"
                    docker run --rm "$TEST_REPO:$IMAGE_TAG" pytest -q -p no:cacheprovider

                    echo "== Smoke tests: test container -> runtime container"
                    docker run -d --name "aceest-app-$BUILD_NUMBER" --network "$NET" \
                      -e DEPLOYMENT_TRACK=ci "$IMAGE_REPO:$IMAGE_TAG"
                    docker run --rm --network "$NET" \
                      -e SMOKE_BASE_URL="http://aceest-app-$BUILD_NUMBER:5000" \
                      -e SMOKE_EXPECT_VERSION="$APP_VERSION" -e SMOKE_EXPECT_TRACK=ci \
                      "$TEST_REPO:$IMAGE_TAG" pytest -v -p no:cacheprovider tests/smoke
                    test "$(docker exec "aceest-app-$BUILD_NUMBER" id -u)" = "10001"
                '''
            }
        }

        stage('Push to Docker Hub') {
            when { expression { params.PUSH_IMAGES } }
            steps {
                withCredentials([usernamePassword(credentialsId: 'dockerhub-creds',
                                                  usernameVariable: 'DH_USER', passwordVariable: 'DH_TOKEN')]) {
                    sh '''
                        echo "$DH_TOKEN" | docker login -u "$DH_USER" --password-stdin
                        for t in "$IMAGE_TAG" "$BUILD_TAG_FULL" latest; do docker push "$IMAGE_REPO:$t"; done
                        for t in "$IMAGE_TAG" latest; do docker push "$TEST_REPO:$t"; done
                        docker logout
                    '''
                }
            }
        }

        stage('Build Artifacts') {
            steps {
                sh '''
                    NAME="aceest-fitness-$APP_VERSION-b$BUILD_NUMBER"
                    git archive --format=tar.gz --prefix="aceest-fitness-$APP_VERSION/" -o "dist/$NAME-src.tar.gz" HEAD
                    tar -czf "dist/$NAME-k8s.tar.gz" k8s
                    DIGEST="$(docker inspect --format='{{index .RepoDigests 0}}' "$IMAGE_REPO:$IMAGE_TAG" 2>/dev/null || echo not-pushed)"
                    cat > "dist/$NAME-build-info.json" <<JSON
{
  "application": "ACEest Fitness & Gym",
  "version": "$APP_VERSION",
  "build": "$BUILD_NUMBER",
  "commit": "$(git rev-parse HEAD)",
  "image": "$IMAGE_REPO:$IMAGE_TAG",
  "image_build_tag": "$IMAGE_REPO:$BUILD_TAG_FULL",
  "image_digest": "$DIGEST",
  "test_image": "$TEST_REPO:$IMAGE_TAG",
  "built_at": "$(date -u +%Y-%m-%dT%H:%M:%SZ)"
}
JSON
                    ls -l dist
                '''
                archiveArtifacts artifacts: 'dist/*', fingerprint: true
            }
        }

        stage('Deploy to Kubernetes') {
            when { expression { params.DEPLOY_STRATEGY != 'none' } }
            steps {
                script { env.DEPLOY_STARTED = 'true' }
                withCredentials([file(credentialsId: 'minikube-kubeconfig', variable: 'KUBECONFIG')]) {
                    withEnv(["TEST_IMAGE=${env.TEST_REPO}:${env.IMAGE_TAG}", "NEW_TAG=${env.IMAGE_TAG}"]) {
                        sh '''
                            S=k8s/scripts
                            kubectl version --client
                            if ! kubectl get namespace aceest >/dev/null 2>&1; then
                                echo "First deployment: bootstrapping all strategies ($STABLE_TAG -> $NEW_TAG)"
                                $S/bootstrap.sh
                            fi
                            deploy() {
                                case "$1" in
                                  rolling)
                                    if [ "$SIMULATE_FAILURE" = "true" ]; then
                                      FAULT_INJECTION=health $S/rolling-update.sh "$IMAGE_TAG" || {
                                        echo "Rollback drill: release rejected and reverted as expected"; return 0; }
                                      echo "Rollback drill expected a failure"; return 1
                                    fi
                                    $S/rolling-update.sh "$IMAGE_TAG" ;;
                                  blue-green) $S/blue-green.sh deploy "$IMAGE_TAG" ;;
                                  canary)
                                    $S/canary.sh start "$IMAGE_TAG" "$CANARY_WEIGHT"
                                    if [ "$PROMOTE" = "true" ]; then $S/canary.sh promote; fi ;;
                                  ab-test)
                                    $S/ab-test.sh deploy "$IMAGE_TAG"
                                    $S/ab-test.sh split 50 ;;
                                  shadow)
                                    $S/shadow.sh deploy "$IMAGE_TAG"
                                    if [ "$PROMOTE" = "true" ]; then $S/shadow.sh promote; fi ;;
                                esac
                            }
                            if [ "$DEPLOY_STRATEGY" = "all" ]; then
                                for s in rolling blue-green canary ab-test shadow; do deploy "$s"; done
                            else
                                deploy "$DEPLOY_STRATEGY"
                            fi
                            $S/status.sh
                        '''
                    }
                }
            }
        }
    }

    post {
        always {
            junit allowEmptyResults: true, testResults: 'reports/junit.xml'
            archiveArtifacts artifacts: 'reports/**', allowEmptyArchive: true
        }
        failure {
            script {
                if (env.DEPLOY_STARTED == 'true') {
                    echo "Deployment failed - reverting ${params.DEPLOY_STRATEGY} to the last stable version"
                    withCredentials([file(credentialsId: 'minikube-kubeconfig', variable: 'KUBECONFIG')]) {
                        sh "k8s/scripts/rollback.sh ${params.DEPLOY_STRATEGY} || true"
                    }
                }
            }
        }
        success {
            echo "Released ${env.IMAGE_REPO}:${env.IMAGE_TAG} with strategy ${params.DEPLOY_STRATEGY}"
        }
    }
}
