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
                python -m venv venv
                . venv/bin/activate
                pip install -r requirements.txt
                '''
            }
        }
        stage('Start App') {
            steps {
                sh '''
                nohup flask --app app run --port 5000 > flask.log 2>&1 &
                sleep 5
                '''
            }
        }
    }
}