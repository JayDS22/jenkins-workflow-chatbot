#!/usr/bin/env bash
# ============================================================================
# create_test_jobs.sh - Sets up demo jobs in your local Jenkins instance
#
# These jobs give the chatbot real data to work with during demos.
# You need three things for a compelling demo:
#   1. A job that succeeds (proves the context reader works on healthy jobs)
#   2. A job that fails with a clear error (the troubleshoot agent's showpiece)
#   3. A job that fails realistically (npm not found - a very common real error)
#
# Prerequisites:
#   - Jenkins running on localhost:8080
#   - curl installed
#   - Your Jenkins API token (get it from: User > Configure > API Token)
#
# Usage:
#   chmod +x scripts/create_test_jobs.sh
#   JENKINS_USER=admin JENKINS_TOKEN=your_token ./scripts/create_test_jobs.sh
# ============================================================================

set -euo pipefail

JENKINS_URL="${JENKINS_URL:-http://localhost:8080}"
JENKINS_USER="${JENKINS_USER:-admin}"
JENKINS_TOKEN="${JENKINS_TOKEN:-}"

if [ -z "$JENKINS_TOKEN" ]; then
    echo "Error: JENKINS_TOKEN is required."
    echo "Get your token from: Jenkins > Your User > Configure > API Token"
    echo ""
    echo "Usage: JENKINS_USER=admin JENKINS_TOKEN=your_token $0"
    exit 1
fi

AUTH="${JENKINS_USER}:${JENKINS_TOKEN}"
CRUMB=$(curl -s -u "$AUTH" "${JENKINS_URL}/crumbIssuer/api/json" | python3 -c "import sys,json; print(json.load(sys.stdin)['crumb'])" 2>/dev/null || echo "")

# Helper to get the crumb header if CSRF protection is enabled
CRUMB_HEADER=""
if [ -n "$CRUMB" ]; then
    CRUMB_HEADER="-H Jenkins-Crumb:${CRUMB}"
fi

echo "Creating test jobs in Jenkins at ${JENKINS_URL}..."
echo ""

# --------------------------------------------------------------------------
# Job 1: hello-pipeline - a simple successful pipeline
# --------------------------------------------------------------------------
echo "[1/3] Creating 'hello-pipeline' (should succeed)..."

cat <<'PIPELINE_XML' > /tmp/hello-pipeline.xml
<?xml version='1.1' encoding='UTF-8'?>
<flow-definition plugin="workflow-job">
  <description>Simple successful pipeline for demo purposes</description>
  <definition class="org.jenkinsci.plugins.workflow.cps.CpsFlowDefinition" plugin="workflow-cps">
    <script>
pipeline {
    agent any
    stages {
        stage('Build') {
            steps {
                echo 'Building the project...'
                sh 'echo "Compile step complete"'
            }
        }
        stage('Test') {
            steps {
                echo 'Running tests...'
                sh 'echo "All 42 tests passed"'
            }
        }
        stage('Deploy') {
            steps {
                echo 'Deploying to staging...'
                sh 'echo "Deployment successful"'
            }
        }
    }
    post {
        success {
            echo 'Pipeline completed successfully!'
        }
    }
}
    </script>
    <sandbox>true</sandbox>
  </definition>
</flow-definition>
PIPELINE_XML

curl -s -u "$AUTH" $CRUMB_HEADER \
    -X POST "${JENKINS_URL}/createItem?name=hello-pipeline" \
    -H "Content-Type: application/xml" \
    --data-binary @/tmp/hello-pipeline.xml \
    -o /dev/null -w "  HTTP %{http_code}\n" || echo "  (may already exist)"

# Trigger a build
curl -s -u "$AUTH" $CRUMB_HEADER \
    -X POST "${JENKINS_URL}/job/hello-pipeline/build" \
    -o /dev/null -w "  Build triggered: HTTP %{http_code}\n"

echo ""

# --------------------------------------------------------------------------
# Job 2: broken-pipeline - fails at the Test stage
# --------------------------------------------------------------------------
echo "[2/3] Creating 'broken-pipeline' (should fail at Test stage)..."

cat <<'PIPELINE_XML' > /tmp/broken-pipeline.xml
<?xml version='1.1' encoding='UTF-8'?>
<flow-definition plugin="workflow-job">
  <description>Pipeline that fails at the Test stage for troubleshooting demo</description>
  <definition class="org.jenkinsci.plugins.workflow.cps.CpsFlowDefinition" plugin="workflow-cps">
    <script>
pipeline {
    agent any
    stages {
        stage('Build') {
            steps {
                echo 'Starting build...'
                sh 'echo "Build OK"'
            }
        }
        stage('Test') {
            steps {
                echo 'Running tests...'
                sh 'exit 1'
            }
        }
        stage('Deploy') {
            steps {
                echo 'This stage will never run'
            }
        }
    }
}
    </script>
    <sandbox>true</sandbox>
  </definition>
</flow-definition>
PIPELINE_XML

curl -s -u "$AUTH" $CRUMB_HEADER \
    -X POST "${JENKINS_URL}/createItem?name=broken-pipeline" \
    -H "Content-Type: application/xml" \
    --data-binary @/tmp/broken-pipeline.xml \
    -o /dev/null -w "  HTTP %{http_code}\n" || echo "  (may already exist)"

curl -s -u "$AUTH" $CRUMB_HEADER \
    -X POST "${JENKINS_URL}/job/broken-pipeline/build" \
    -o /dev/null -w "  Build triggered: HTTP %{http_code}\n"

echo ""

# --------------------------------------------------------------------------
# Job 3: npm-build - realistic failure (npm not found)
# --------------------------------------------------------------------------
echo "[3/3] Creating 'npm-build' (should fail - npm not found)..."

cat <<'PIPELINE_XML' > /tmp/npm-build.xml
<?xml version='1.1' encoding='UTF-8'?>
<flow-definition plugin="workflow-job">
  <description>Realistic build failure - npm not found on agent</description>
  <definition class="org.jenkinsci.plugins.workflow.cps.CpsFlowDefinition" plugin="workflow-cps">
    <script>
pipeline {
    agent any
    stages {
        stage('Install Dependencies') {
            steps {
                echo 'Installing Node.js dependencies...'
                sh 'npm install'
            }
        }
        stage('Lint') {
            steps {
                sh 'npm run lint'
            }
        }
        stage('Build') {
            steps {
                sh 'npm run build'
            }
        }
        stage('Test') {
            steps {
                sh 'npm test'
            }
        }
    }
}
    </script>
    <sandbox>true</sandbox>
  </definition>
</flow-definition>
PIPELINE_XML

curl -s -u "$AUTH" $CRUMB_HEADER \
    -X POST "${JENKINS_URL}/createItem?name=npm-build" \
    -H "Content-Type: application/xml" \
    --data-binary @/tmp/npm-build.xml \
    -o /dev/null -w "  HTTP %{http_code}\n" || echo "  (may already exist)"

curl -s -u "$AUTH" $CRUMB_HEADER \
    -X POST "${JENKINS_URL}/job/npm-build/build" \
    -o /dev/null -w "  Build triggered: HTTP %{http_code}\n"

echo ""

# Cleanup temp files
rm -f /tmp/hello-pipeline.xml /tmp/broken-pipeline.xml /tmp/npm-build.xml

echo "Done! All three test jobs have been created and triggered."
echo ""
echo "Wait ~30 seconds for the builds to complete, then test the chatbot:"
echo ""
echo '  curl -X POST http://localhost:8000/api/chat \'
echo '    -H "Content-Type: application/json" \'
echo '    -d '"'"'{"query": "Why did my build fail?", "job_name": "broken-pipeline"}'"'"
echo ""
echo "That query is the showstopper demo - it reads the actual build log."
