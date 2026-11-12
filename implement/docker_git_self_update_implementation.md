# Self-Updating Dockerized Webapp via Git

## Overview

This document describes a safe architecture for allowing a Dockerized internal web application to update itself from a Git repository.

The intended workflow is:

1. Develop changes locally.
2. Commit and push changes to Git/Gitea.
3. Open the deployed web application.
4. The web application checks whether a newer Git commit exists.
5. An authorized administrator clicks **Update Application**.
6. The web application sends a deployment request to a separate deployment service.
7. The deployment service:
   - pulls the latest Git changes
   - builds a new Docker image
   - stops the old application container
   - starts the new application container
   - performs a health check
   - rolls back if the deployment fails

The main web application should **not directly control the Docker daemon**.

---

# Architecture

```text
Developer Machine
      |
      | git push
      v
Private Git / Gitea Repository
      ^
      |
      | git fetch / git pull
      |
+-------------------------------+
| Deployment Service            |
| Running on Docker Host        |
|                               |
| - Authentication              |
| - Git operations              |
| - Docker build                |
| - Container restart           |
| - Health checks               |
| - Deployment logging          |
| - Rollback                    |
+---------------+---------------+
                ^
                |
                | HTTP API
                |
+---------------+---------------+
| Web Application Container     |
|                               |
| Admin Update Page             |
|                               |
| Current Version               |
| Remote Version                |
| Update Button                 |
+-------------------------------+
```

---

# Important Security Rule

Do **not** give the main web application direct access to the Docker daemon.

Avoid mounting:

Linux:

```text
/var/run/docker.sock
```

Windows:

```text
//./pipe/docker_engine
```

directly into the main web application.

Docker daemon access is highly privileged. If the application is compromised, an attacker could potentially control containers or the Docker host.

Instead, create a small dedicated **Deployment Service** with tightly controlled functionality.

---

# Recommended Project Structure

Example Windows Server structure:

```text
C:\apps\SRM-WebApp\
│
├── repo\
│   ├── app.py
│   ├── requirements.txt
│   ├── Dockerfile
│   ├── docker-compose.yml
│   └── ...
│
├── deploy\
│   ├── deploy.py
│   ├── deploy.bat
│   ├── rollback.bat
│   └── deployment_logs\
│
└── config\
    └── deployment.env
```

Recommended logical components:

```text
Developer PC
    |
    v
Gitea
    |
    v
Deployment Service
    |
    +--> Git Repository
    |
    +--> Docker Engine
    |
    +--> Deployment Logs
    |
    +--> Health Check
    |
    +--> Rollback
```

---

# Deployment Workflow

## Step 1 - Developer Pushes Changes

From the development machine:

```bash
git add .
git commit -m "Update application"
git push origin main
```

The production server should deploy only from a trusted branch such as:

```text
main
```

or:

```text
production
```

Do not allow the web application to submit arbitrary Git branches or repository URLs.

---

# Step 2 - Webapp Checks for Updates

The production application should display information such as:

```text
Current Version
Commit: 81f2a6c
Status: Running

Remote Version
Commit: a34bc91
Status: Update Available

[ Update Application ]
```

The application can obtain the currently deployed commit from:

```bash
git rev-parse HEAD
```

The latest remote commit can be checked using:

```bash
git fetch origin
git rev-parse origin/main
```

Comparison logic:

```text
current_commit == remote_commit
```

means:

```text
Application is up to date
```

Otherwise:

```text
Update available
```

---

# Step 3 - Update Button

The web application should **not perform Git or Docker commands directly**.

Instead:

```text
Webapp
   |
   | POST /deploy
   v
Deployment Service
```

Example:

```python
import requests

def update_application():
    response = requests.post(
        "http://deployment-service:9000/deploy",
        timeout=10,
    )

    response.raise_for_status()

    return response.json()
```

Example API response:

```json
{
  "deployment_id": "deploy-20260928-001",
  "status": "queued"
}
```

---

# Why Deployment Should Be Separate

The currently running application container may be stopped during deployment.

For example:

```text
Webapp
   |
   | POST /deploy
   v
Deployment Service
   |
   +--> docker stop webapp
```

Once the container stops, it cannot continue processing the original request.

Therefore, deployment should be handled by an independent process or service that remains running while the main application is replaced.

---

# Deployment Status API

Recommended endpoints:

```text
POST /deploy
GET  /deploy/{deployment_id}
GET  /version
POST /rollback
```

Example:

```text
POST /deploy
```

Response:

```json
{
  "deployment_id": "deploy-20260928-001",
  "status": "started"
}
```

The web application should then poll:

```text
GET /deploy/deploy-20260928-001
```

Possible responses:

```json
{
  "status": "pulling"
}
```

```json
{
  "status": "building"
}
```

```json
{
  "status": "restarting"
}
```

```json
{
  "status": "health_check"
}
```

```json
{
  "status": "success",
  "commit": "a34bc91"
}
```

Failure example:

```json
{
  "status": "failed",
  "message": "Docker image build failed"
}
```

---

# Example Deployment Script

Example Windows batch file:

```bat
@echo off

set APP_DIR=C:\apps\SRM-WebApp\repo
set IMAGE_NAME=srm-webapp
set CONTAINER_NAME=srm-webapp

cd /d %APP_DIR%

echo =========================================
echo Fetching latest repository changes
echo =========================================

git fetch origin

if errorlevel 1 (
    echo Git fetch failed.
    exit /b 1
)

echo =========================================
echo Pulling latest main branch
echo =========================================

git pull origin main

if errorlevel 1 (
    echo Git pull failed.
    exit /b 1
)

echo =========================================
echo Reading Git commit
echo =========================================

for /f %%i in ('git rev-parse --short HEAD') do set COMMIT=%%i

echo Deploying commit: %COMMIT%

echo =========================================
echo Building Docker image
echo =========================================

docker build -t %IMAGE_NAME%:%COMMIT% .

if errorlevel 1 (
    echo Docker build failed.
    exit /b 1
)

echo =========================================
echo Stopping existing container
echo =========================================

docker stop %CONTAINER_NAME%

echo =========================================
echo Removing existing container
echo =========================================

docker rm %CONTAINER_NAME%

echo =========================================
echo Starting new container
echo =========================================

docker run -d ^
    --name %CONTAINER_NAME% ^
    --restart unless-stopped ^
    -p 8501:8501 ^
    %IMAGE_NAME%:%COMMIT%

if errorlevel 1 (
    echo Failed to start container.
    exit /b 1
)

echo =========================================
echo Deployment complete
echo =========================================

echo Commit: %COMMIT%
```

---

# Docker Image Versioning

Avoid relying only on:

```text
srm-webapp:latest
```

Instead, tag images using the Git commit:

```text
srm-webapp:a34bc91
srm-webapp:81f2a6c
srm-webapp:f431dda
```

This provides a direct relationship between:

```text
Git commit
      |
      v
Docker image
```

Example:

```bash
docker build -t srm-webapp:a34bc91 .
```

This makes rollback much easier.

---

# Rollback Strategy

Never immediately delete the previous Docker image.

Assume:

```text
Current version:
srm-webapp:a34bc91

Previous version:
srm-webapp:81f2a6c
```

If deployment fails:

```bash
docker stop srm-webapp
docker rm srm-webapp
```

Then start the previous image:

```bash
docker run -d \
    --name srm-webapp \
    --restart unless-stopped \
    -p 8501:8501 \
    srm-webapp:81f2a6c
```

Windows equivalent:

```bat
docker run -d ^
    --name srm-webapp ^
    --restart unless-stopped ^
    -p 8501:8501 ^
    srm-webapp:81f2a6c
```

---

# Health Check

A deployment should not be considered successful simply because:

```bash
docker run
```

succeeded.

The deployment service should verify that the application is responding.

Recommended endpoint:

```text
GET /health
```

Example response:

```json
{
  "status": "healthy"
}
```

Example FastAPI endpoint:

```python
@app.get("/health")
def health():
    return {
        "status": "healthy"
    }
```

Example Flask endpoint:

```python
@app.route("/health")
def health():
    return {
        "status": "healthy"
    }
```

The deployment flow should be:

```text
docker build
     |
     v
start container
     |
     v
wait for application startup
     |
     v
GET /health
     |
     +---- healthy ----> deployment success
     |
     +---- failed -----> rollback
```

---

# Recommended Deployment State Machine

Use statuses such as:

```text
queued
fetching
pulling
building
starting
health_check
success
failed
rolling_back
rolled_back
```

Example lifecycle:

```text
queued
   |
   v
fetching
   |
   v
pulling
   |
   v
building
   |
   v
starting
   |
   v
health_check
   |
   +-------- success
   |
   +-------- failed
                 |
                 v
             rolling_back
                 |
                 v
             rolled_back
```

---

# Update Page Example

The web application admin page could display:

```text
Application Deployment

Current Version
--------------------------------
Commit: 81f2a6c
Branch: main
Status: Running

Latest Repository Version
--------------------------------
Commit: a34bc91

Update Available

[ Update Application ]
```

After clicking:

```text
Deployment Progress

✓ Repository fetched
✓ Latest commit pulled
✓ Docker image built
✓ New container started
✓ Health check passed

Deployment Successful

Version:
a34bc91
```

---

# Disable Multiple Deployments

Only one deployment should run at a time.

For example:

```python
deployment_running = True
```

If another request arrives:

```json
{
  "status": "deployment_in_progress"
}
```

The Update button should also be disabled while deployment is running.

Example UI:

```text
[ Updating... ]
```

instead of:

```text
[ Update Application ]
```

---

# Authentication

The deployment endpoint should only be accessible by authorized administrators.

Do not expose:

```text
POST /deploy
```

to all application users.

Recommended checks:

```text
Authenticated user
        |
        v
Has deployment/admin role?
        |
       YES
        |
        v
Allow deployment
```

Otherwise:

```text
403 Forbidden
```

---

# Audit Logging

Every deployment should be logged.

Recommended fields:

```text
deployment_id
requested_by
requested_at
previous_commit
new_commit
branch
build_status
deployment_status
health_check_status
rollback_status
completed_at
```

Example:

```json
{
  "deployment_id": "deploy-20260928-001",
  "requested_by": "admin-user",
  "requested_at": "2026-09-28T10:40:00+08:00",
  "previous_commit": "81f2a6c",
  "new_commit": "a34bc91",
  "branch": "main",
  "status": "success"
}
```

---

# Git Safety Checks

Before deployment, verify the working tree.

Run:

```bash
git status --porcelain
```

If the output is not empty, production files have local modifications.

The deployment should normally stop instead of blindly overwriting them.

Example:

```text
Deployment aborted.

Production repository contains local modifications.
```

Production should ideally never contain manually edited application files.

All changes should come from Git.

---

# Recommended Git Commands

A safer production workflow is:

```bash
git fetch origin
git checkout main
git reset --hard origin/main
```

instead of:

```bash
git pull origin main
```

Why?

Production should normally exactly match the repository.

Using:

```bash
git reset --hard origin/main
```

prevents unexpected merge commits or merge conflicts on the production server.

Important:

This command deletes local Git-tracked modifications.

Only use it if production application files are never manually edited.

---

# Recommended Production Deployment Flow

Recommended sequence:

```text
1. Receive deployment request
2. Validate administrator permissions
3. Check deployment lock
4. Record current Git commit
5. git fetch origin
6. verify target branch
7. git reset --hard origin/main
8. read new Git commit
9. docker build with commit tag
10. start replacement container
11. perform health check
12. mark deployment successful
13. retain previous image for rollback
14. write deployment log
```

---

# Better Container Replacement Strategy

Stopping the production container before verifying the new image causes downtime.

A better strategy is:

```text
Current container
Port 8501
      |
      v
Users
```

Build the new version first:

```text
docker build
```

Then start it temporarily on another port:

```text
New container
Port 8502
```

Health check:

```text
http://localhost:8502/health
```

If healthy:

```text
switch traffic
```

Then remove the old version.

This becomes easier when using a reverse proxy such as:

```text
Nginx
Traefik
IIS
```

Architecture:

```text
Users
   |
   v
Reverse Proxy
   |
   v
Current Application Container
```

During deployment:

```text
Users
   |
   v
Reverse Proxy
   |
   +---- old container
   |
   +---- new container
```

After the new container passes health checks:

```text
Users
   |
   v
Reverse Proxy
   |
   v
New Application Container
```

Then:

```text
Old Application Container
        |
        v
      remove
```

This allows near-zero-downtime deployments.

---

# Minimal Version for Initial Implementation

For the first version, keep the system simple.

Implement:

```text
Developer
    |
git push
    |
    v
Gitea
    |
    v
Deployment Service
    |
    +--> git fetch
    +--> git reset --hard origin/main
    +--> docker build
    +--> docker stop
    +--> docker rm
    +--> docker run
    +--> health check
```

Then add later:

```text
rollback
deployment history
zero-downtime deployment
reverse proxy switching
automatic deployment
notifications
```

---

# Suggested Deployment Service Structure

```text
deploy/
│
├── app.py
├── deployment.py
├── git_manager.py
├── docker_manager.py
├── health.py
├── state.py
├── config.py
├── requirements.txt
│
└── logs/
```

Suggested responsibilities:

## `app.py`

Deployment API.

Example endpoints:

```text
POST /deploy
GET /deploy/{id}
GET /version
POST /rollback
GET /health
```

---

## `git_manager.py`

Responsible for:

```text
git fetch
git status
git reset
git rev-parse
commit comparison
```

---

## `docker_manager.py`

Responsible for:

```text
docker build
docker run
docker stop
docker rm
docker inspect
Docker image tagging
```

---

## `health.py`

Responsible for:

```text
application health checks
retry logic
timeout logic
```

---

## `state.py`

Responsible for:

```text
deployment status
deployment ID
deployment locking
deployment history
```

---

# Security Requirements

Implement the following rules:

- Deployment endpoint must require authentication.
- Deployment endpoint must require administrator authorization.
- Only a predefined Git repository may be deployed.
- Only predefined branches may be deployed.
- Never accept arbitrary shell commands from the frontend.
- Never accept arbitrary Docker commands from the frontend.
- Never accept arbitrary repository URLs.
- Never expose Docker daemon access to the web application.
- Store Git credentials securely.
- Store deployment secrets outside source code.
- Log every deployment attempt.
- Run the deployment service only inside the trusted internal network.

---

# Do Not Implement This

Avoid code such as:

```python
command = request.json["command"]

subprocess.run(
    command,
    shell=True
)
```

This is effectively remote command execution.

Also avoid:

```python
repository = request.json["repository"]
branch = request.json["branch"]

subprocess.run(
    f"git clone {repository}",
    shell=True
)
```

The deployment service should use configuration controlled by the server.

Example:

```python
REPOSITORY = "configured-on-server"
BRANCH = "main"
IMAGE_NAME = "srm-webapp"
CONTAINER_NAME = "srm-webapp"
```

The frontend should only request:

```text
Deploy the approved application
```

not tell the server how to deploy it.

---

# Future Improvement: Automatic Deployment

Eventually, instead of requiring:

```text
[ Update Application ]
```

you can use a Gitea webhook.

Architecture:

```text
Developer
    |
    | git push
    v
Gitea
    |
    | webhook
    v
Deployment Service
    |
    v
Docker deployment
```

Example:

```text
Push to main
       |
       v
POST /webhook/gitea
       |
       v
Verify webhook secret
       |
       v
Start deployment
```

For initial implementation, manual deployment through an authenticated admin page is easier to control.

---

# Recommended Initial Goal

Implement the following first:

```text
[1] Deployment service

[2] POST /deploy

[3] GET /deploy/{id}

[4] Git fetch/reset

[5] Docker image build

[6] Git-commit Docker tags

[7] Container restart

[8] Health check

[9] Deployment logs

[10] Admin-only Update button
```

After that works reliably, implement:

```text
rollback
deployment history UI
zero-downtime replacement
reverse proxy
Gitea webhook
```

---

# Final Architecture

```text
                 DEVELOPMENT

Developer Machine
        |
        | git commit
        | git push
        v
+-----------------------+
| Private Gitea Server  |
+-----------+-----------+
            |
            |
            v

                 PRODUCTION

+-------------------------------+
| Deployment Service            |
|                               |
| Git Manager                   |
| Docker Manager                |
| Health Checker                |
| Deployment State              |
| Logging                       |
+---------------+---------------+
                |
                |
        +-------+-------+
        |               |
        v               v
 Git Repository     Docker Engine
                        |
                        v
                +---------------+
                | Webapp        |
                | Container     |
                +-------+-------+
                        |
                        v
                     Users
```

The web application communicates with the deployment service:

```text
Admin User
    |
    v
Webapp
    |
    | POST /deploy
    v
Deployment Service
    |
    +--> Git
    |
    +--> Docker
    |
    +--> Health Check
    |
    +--> Deployment Log
```

This keeps the deployment mechanism separated from the application being deployed and avoids giving the main application unrestricted access to the Docker host.
