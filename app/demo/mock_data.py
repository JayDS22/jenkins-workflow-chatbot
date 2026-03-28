"""
Demo Data Provider - makes the PoC demo-ready without a Jenkins instance.

When a reviewer clones this repo and runs it without Docker/Jenkins,
they should still see the full power of the multi-agent system.
This module provides realistic mock data that looks exactly like
what python-jenkins returns from a real Jenkins instance.

The build logs are modeled after actual failures I've debugged in
production Jenkins at Bridgestone - npm not found, permission denied,
test failures with stack traces, Docker build errors. These are the
errors that Jenkins admins deal with every day.
"""


def get_demo_server_info() -> dict:
    """Mock Jenkins server state with realistic plugin list."""
    return {
        "jenkins_version": "2.541.3 (demo mode)",
        "installed_plugins": [
            "git", "github", "github-api", "github-branch-source",
            "pipeline-model-definition", "workflow-aggregator", "workflow-cps",
            "workflow-job", "workflow-multibranch", "workflow-step-api",
            "docker-workflow", "docker-commons", "docker-java-api",
            "credentials", "credentials-binding", "ssh-credentials",
            "plain-credentials", "matrix-auth", "role-strategy",
            "cloudbees-folder", "antisamy-markup-formatter",
            "build-timeout", "timestamper", "ws-cleanup",
            "gradle", "maven-plugin", "ant",
            "pipeline-stage-view", "blueocean",
            "configuration-as-code", "job-dsl",
            "junit", "htmlpublisher", "cobertura",
            "email-ext", "mailer",
            "prometheus", "metrics",
            "pipeline-utility-steps", "pipeline-input-step",
            "lockable-resources", "throttle-concurrents",
            "rebuild", "parameterized-trigger",
            "script-security", "permissive-script-security",
        ],
        "plugin_count": 42,
        "jobs": [
            "hello-pipeline",
            "broken-pipeline",
            "npm-build",
            "backend-api-deploy",
            "frontend-build",
            "nightly-integration-tests",
        ],
        "job_count": 6,
        "connected": False,
        "demo_mode": True,
        "note": "Running in demo mode with realistic mock data. Connect to a real Jenkins for live context.",
    }


def get_demo_build_log(job_name: str) -> dict:
    """Return realistic build log data for demo jobs."""

    logs = {
        "broken-pipeline": {
            "job_name": "broken-pipeline",
            "build_number": 7,
            "result": "FAILURE",
            "duration_ms": 4230,
            "timestamp": 1711584000000,
            "console_tail": """Started by user admin
Running in Durability level: MAX_SURVIVABILITY
[Pipeline] Start of Pipeline
[Pipeline] node
Running on Jenkins in /var/jenkins_home/workspace/broken-pipeline
[Pipeline] {
[Pipeline] stage
[Pipeline] { (Build)
[Pipeline] echo
Starting build...
[Pipeline] sh
+ echo Build OK
Build OK
[Pipeline] }
[Pipeline] // stage
[Pipeline] stage
[Pipeline] { (Test)
[Pipeline] echo
Running tests...
[Pipeline] sh
+ exit 1
[Pipeline] }
[Pipeline] // stage
[Pipeline] }
[Pipeline] // node
[Pipeline] End of Pipeline
ERROR: script returned exit code 1
Finished: FAILURE""",
            "error_lines": [
                "ERROR: script returned exit code 1",
                "Finished: FAILURE",
            ],
            "full_log_length": 847,
        },
        "npm-build": {
            "job_name": "npm-build",
            "build_number": 3,
            "result": "FAILURE",
            "duration_ms": 2150,
            "timestamp": 1711584300000,
            "console_tail": """Started by user admin
Running in Durability level: MAX_SURVIVABILITY
[Pipeline] Start of Pipeline
[Pipeline] node
Running on Jenkins in /var/jenkins_home/workspace/npm-build
[Pipeline] {
[Pipeline] stage
[Pipeline] { (Install Dependencies)
[Pipeline] echo
Installing Node.js dependencies...
[Pipeline] sh
+ npm install
/var/jenkins_home/workspace/npm-build@tmp/durable-6b1c4a12/script.sh: line 1: npm: not found
[Pipeline] }
[Pipeline] // stage
[Pipeline] }
[Pipeline] // node
[Pipeline] End of Pipeline
ERROR: script returned exit code 127
Finished: FAILURE""",
            "error_lines": [
                "/var/jenkins_home/workspace/npm-build@tmp/durable-6b1c4a12/script.sh: line 1: npm: not found",
                "ERROR: script returned exit code 127",
                "Finished: FAILURE",
            ],
            "full_log_length": 623,
        },
        "backend-api-deploy": {
            "job_name": "backend-api-deploy",
            "build_number": 24,
            "result": "FAILURE",
            "duration_ms": 45600,
            "timestamp": 1711583700000,
            "console_tail": """[Pipeline] stage
[Pipeline] { (Docker Build)
[Pipeline] sh
+ docker build -t backend-api:latest .
Sending build context to Docker daemon  45.3MB
Step 1/12 : FROM python:3.11-slim
 ---> 2a7b4f8c1234
Step 2/12 : WORKDIR /app
 ---> Using cache
 ---> 8f7a6b5c4321
Step 3/12 : COPY requirements.txt .
 ---> Using cache
 ---> 3c4d5e6f7890
Step 4/12 : RUN pip install --no-cache-dir -r requirements.txt
 ---> Running in 9a8b7c6d5432
ERROR: Could not find a version that satisfies the requirement torch==2.1.0 (from versions: none)
ERROR: No matching distribution found for torch==2.1.0
The command '/bin/sh -c pip install --no-cache-dir -r requirements.txt' returned a non-zero code: 1
[Pipeline] }
[Pipeline] // stage
ERROR: script returned exit code 1
Finished: FAILURE""",
            "error_lines": [
                "ERROR: Could not find a version that satisfies the requirement torch==2.1.0 (from versions: none)",
                "ERROR: No matching distribution found for torch==2.1.0",
                "The command '/bin/sh -c pip install --no-cache-dir -r requirements.txt' returned a non-zero code: 1",
                "ERROR: script returned exit code 1",
                "Finished: FAILURE",
            ],
            "full_log_length": 3847,
        },
        "nightly-integration-tests": {
            "job_name": "nightly-integration-tests",
            "build_number": 156,
            "result": "FAILURE",
            "duration_ms": 182400,
            "timestamp": 1711551600000,
            "console_tail": """[Pipeline] stage
[Pipeline] { (Integration Tests)
[Pipeline] sh
+ pytest tests/integration/ -v --tb=short
============================= test session starts ==============================
platform linux -- Python 3.11.7, pytest-8.3.4, pluggy-1.5.0
collected 47 items

tests/integration/test_api_endpoints.py::test_health_check PASSED       [  2%]
tests/integration/test_api_endpoints.py::test_create_user PASSED        [  4%]
tests/integration/test_api_endpoints.py::test_auth_flow PASSED          [  6%]
tests/integration/test_database.py::test_connection_pool PASSED         [  8%]
tests/integration/test_database.py::test_migration_rollback FAILED      [ 10%]

FAILED tests/integration/test_database.py::test_migration_rollback
  assert result.exit_code == 0
  AssertionError: assert 1 == 0
  E   psycopg2.OperationalError: connection to server at "db-staging.internal" (10.0.3.42), port 5432 failed: Connection timed out
  E       Is the server running on that host and accepting TCP/IP connections?

tests/integration/test_external_api.py::test_payment_webhook FAILED     [ 12%]

FAILED tests/integration/test_external_api.py::test_payment_webhook
  requests.exceptions.ConnectionError: HTTPSConnectionPool(host='api.stripe.com', port=443): Max retries exceeded

====================== 2 failed, 45 passed in 182.4s =======================
[Pipeline] junit
Recording test results
[Pipeline] }
ERROR: There were test failures.
Finished: UNSTABLE""",
            "error_lines": [
                "FAILED tests/integration/test_database.py::test_migration_rollback",
                "psycopg2.OperationalError: connection to server at \"db-staging.internal\" (10.0.3.42), port 5432 failed: Connection timed out",
                "FAILED tests/integration/test_external_api.py::test_payment_webhook",
                "requests.exceptions.ConnectionError: HTTPSConnectionPool(host='api.stripe.com', port=443): Max retries exceeded",
                "ERROR: There were test failures.",
            ],
            "full_log_length": 12453,
        },
    }

    if job_name in logs:
        return logs[job_name]

    # Default successful build for unknown jobs
    return {
        "job_name": job_name,
        "build_number": 1,
        "result": "SUCCESS",
        "duration_ms": 3200,
        "timestamp": 1711584600000,
        "console_tail": f"[Pipeline] echo\nBuild completed successfully\nFinished: SUCCESS",
        "error_lines": [],
        "full_log_length": 256,
    }


def get_demo_failed_builds() -> list:
    """Return a summary of demo failed builds."""
    return [
        {
            "job_name": "broken-pipeline",
            "failed_build_number": 7,
            "last_successful": 5,
        },
        {
            "job_name": "npm-build",
            "failed_build_number": 3,
            "last_successful": None,
        },
        {
            "job_name": "backend-api-deploy",
            "failed_build_number": 24,
            "last_successful": 23,
        },
        {
            "job_name": "nightly-integration-tests",
            "failed_build_number": 156,
            "last_successful": 155,
        },
    ]


def get_demo_job_details(job_name: str) -> dict:
    """Return realistic job details for demo mode."""
    jobs = {
        "broken-pipeline": {
            "job_name": "broken-pipeline",
            "url": "http://localhost:8080/job/broken-pipeline/",
            "buildable": True,
            "last_build_number": 7,
            "last_failed_build": 7,
            "health_score": 0,
            "in_queue": False,
        },
        "npm-build": {
            "job_name": "npm-build",
            "url": "http://localhost:8080/job/npm-build/",
            "buildable": True,
            "last_build_number": 3,
            "last_failed_build": 3,
            "health_score": 0,
            "in_queue": False,
        },
        "hello-pipeline": {
            "job_name": "hello-pipeline",
            "url": "http://localhost:8080/job/hello-pipeline/",
            "buildable": True,
            "last_build_number": 12,
            "last_failed_build": None,
            "health_score": 100,
            "in_queue": False,
        },
    }
    return jobs.get(job_name, {"error": f"Job '{job_name}' not found in demo data"})
