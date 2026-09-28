pipeline {
    agent any

    environment {
        PYTHON = 'C:\\Python312\\python.exe'   // change to your path from "where python"
    }

    stages {
        stage('Setup') {
            steps {
                bat '''
                    "%PYTHON%" -m venv venv
                    venv\\Scripts\\python.exe -m pip install --upgrade pip
                    venv\\Scripts\\python.exe -m pip install -r requirements.txt
                '''
            }
        }

        stage('Start App') {
            steps {
                withEnv(['JENKINS_NODE_COOKIE=dontKillMe']) {
                    bat '''
                        start "FlaskApp" /B cmd /c "venv\\Scripts\\python.exe -m flask --app app run --port 5000 > flask.log 2>&1"
                        powershell -Command "for ($i=0; $i -lt 30; $i++) { try { Invoke-WebRequest -UseBasicParsing http://127.0.0.1:5000 | Out-Null; exit 0 } catch { Start-Sleep -Seconds 1 } }; exit 1"
                    '''
                }
            }
        }

//        stage('Test') {
//            steps {
//                bat 'venv\\Scripts\\python.exe -m pytest'
//            }
//        }
    }

    post {
        always {
            bat '''
                for /f "tokens=5" %%a in ('netstat -ano ^| findstr :5000 ^| findstr LISTENING') do taskkill /F /PID %%a
                exit /b 0
            '''
            archiveArtifacts artifacts: 'flask.log', allowEmptyArchive: true
        }
    }
}