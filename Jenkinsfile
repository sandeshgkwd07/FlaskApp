pipeline {
    agent any

    stages {
        stage('Checkout') {
            steps {
                checkout scm
            }
        }

        stage('Setup') {
            steps {
                sh '''
                    python3 -m venv venv
                    . venv/bin/activate
                    pip install --upgrade pip
                    pip install -r requirements.txt
                '''
            }
        }

        stage('Start App') {
            steps {
                withEnv(['JENKINS_NODE_COOKIE=dontKillMe']) {
                    sh '''
                        . venv/bin/activate
                        nohup flask --app app run --port 5000 > flask.log 2>&1 &
                        echo $! > flask.pid

                        # wait up to 30s for the app to respond
                        for i in $(seq 1 30); do
                            curl -s http://127.0.0.1:5000 > /dev/null && exit 0
                            sleep 1
                        done
                        echo "Flask app failed to start"
                        cat flask.log
                        exit 1
                    '''
                }
            }
        }

        stage('Test') {
            steps {
                sh '''
                    . venv/bin/activate
                    pytest
                '''
            }
        }
    }

    post {
        always {
            sh '''
                if [ -f flask.pid ]; then
                    kill $(cat flask.pid) || true
                fi
            '''
            archiveArtifacts artifacts: 'flask.log', allowEmptyArchive: true
        }
    }
}