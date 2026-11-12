# Git and Docker Commands

Run these commands in PowerShell from your project folder.

## Git

Git saves your code history and shares changes with a remote repository.

### Set up your identity (once)

```powershell
git config --global user.name "Rinzai Terrado"
git config --global user.email "rinzai.terrado@okadamanila.com"
```

### Download an existing repository

```powershell
git clone https://gitea.okadamanila.com/Rinzai.Terrado/SRM-Streamlit.git
cd SRM-Streamlit
```

Cloning already sets up Git and the `origin` remote.

### Everyday commands

| Command | Purpose |
| --- | --- |
| `git status` | Show changed files and the current branch. |
| `git diff` | Show changes you have not staged. |
| `git pull --ff-only origin main` | Update from remote `main`; stop if histories have diverged. |
| `git add Documents.md` | Stage a specific file; replace the filename as needed. |
| `git diff --staged` | Review what will be committed. |
| `git commit -m "Update documentation"` | Save staged changes locally. |
| `git push origin main` | Upload local `main` commits. |
| `git log --oneline -5` | Show the last five commits. |

Use the pull/push examples while on `main`. Pull before editing with a clean working folder. After editing: **status -> add -> review -> commit -> push**.

### Pull updates from Git

Pull downloads remote changes and applies them to your current branch. Commit your work first and check that `git status` shows a clean working folder.

```powershell
git status
git switch main
git pull --ff-only origin main
```

`--ff-only` updates your branch without creating a merge commit. If Git reports diverged branches, both local and remote branches have new commits. To combine them with a merge while on `main`:

```powershell
git fetch origin
git merge origin/main
```

`fetch` only downloads updates; `merge` combines them into your current branch. If a commit-message editor opens, save and close it to finish.

### Merge a branch into main

Replace `feature-name` with your branch name. Commit the changes on that branch before switching to `main`.

```powershell
git switch main
git pull --ff-only origin main
git merge feature-name
# After the merge succeeds, check the app, then upload the result.
git push origin main
```

If the pull fails, resolve it before continuing. For a branch that exists only on the remote, run `git fetch origin`, then use `git merge origin/feature-name` instead.

### Resolve merge conflicts

If Git cannot combine changes automatically, the merge pauses:

1. Run `git status` to find conflicting files.
2. Open each file, keep the desired content, and remove the `<<<<<<<`, `=======`, and `>>>>>>>` conflict markers.
3. Stage each resolved file and finish the merge:

```powershell
# Replace the example filename with each file you resolved.
git add Documents.md
git diff --staged
git commit -m "Resolve merge conflicts"
```

Check the app before pushing. To cancel an unfinished merge instead, run `git merge --abort`.

### First push of a new project

Only use this for a new local project and an empty remote repository. Skip it for this existing checkout or a cloned repository. Replace the example URL with your new repository URL.

```powershell
git init -b main
git add .
git diff --staged
git commit -m "Initial commit"
git remote add origin https://gitea.okadamanila.com/Rinzai.Terrado/NEW-REPOSITORY.git
git push -u origin main
```

`git add .` stages all changes under the current folder, except ignored files. Review them before committing.

## Docker

An **image** is the packaged app. A **container** runs that image.

Use a local project copy (for example, `C:\Apps\SRM-Streamlit`) and a Docker engine running Windows containers. Open the app on port **8501**; Docker forwards it to Streamlit on port **8501** inside the container (`8501:8501`). See [README.md](README.md#windows-container-deployment) for the required offline bundles and workbook setup.

### Run with Docker Compose

Compose uses `compose.yaml` and `Dockerfile-streamlit`. Include `wheelhouse_py311`, the four installers listed in `deployment/odbc/README.md`, and the workbook in `data_sources` before building. The custom base image must already be available locally or through the internal registry.

For an offline rebuild and restart:

```powershell
docker compose build --pull=false
docker compose up -d --no-build --pull never
docker compose exec dashboard python C:/app/deployment/verify_odbc.py
```


| Command | Purpose |
| --- | --- |
| `docker compose up -d --build` | Build the image and start the app in the background. |
| `docker compose ps` | Show app status. |
| `docker compose logs -f` | Follow app logs; press Ctrl+C to exit the log view. |
| `docker compose stop` | Stop the app while keeping its container. |
| `docker compose start` | Start the stopped container. |
| `docker compose restart` | Restart the app; does not rebuild code changes. |
| `docker compose down` | Stop and remove the Compose containers and network. |

Open `http://localhost:8501` (unless `APP_PORT` is overridden). After code changes, run `docker compose up -d --build` again.

The production-facing address is intended to be
`https://smart.okadamanila.com`. The reverse proxy terminates TLS and forwards
all HTTP and WebSocket traffic to `http://10.36.27.27:8501`; company DNS, the TLS
certificate, and the proxy rule must exist before that URL will resolve. Check
`http://10.36.27.27:8501/_stcore/health` from the proxy host before publishing it.
See [proxy setup](deployment/proxy/README.md) for the Nginx configuration and activation steps.

### Build and publish the custom image

These commands use the same `Dockerfile-streamlit` as Compose. Its internal base image, `wheelhouse_py311`, and offline ODBC installers must be available. Replace `0.0.1` with your release version.

```powershell
# Build the image
docker build -t streamlit:0.0.1 -f Dockerfile-streamlit .

# Tag it for the internal registry
docker tag streamlit:0.0.1 10.36.27.24:5000/streamlit:0.0.1

# Upload it to the registry
docker push 10.36.27.24:5000/streamlit:0.0.1
```

### Docker Run
Command to run the Docker app 
```
docker run --rm --name streamlit -p 8501:8501 -e STREAMLIT_BROWSER_SERVER_ADDRESS=smart.okadamanila.com -e STREAMLIT_BROWSER_SERVER_PORT=443 streamlit:0.0.1
```

### Other useful commands

| Command | Purpose |
| --- | --- |
| `docker images` | List local images. |
| `docker ps` | List running containers. |
| `docker ps -a` | List all containers, including stopped ones. |
| `docker logs -f CONTAINER` | Follow logs; replace `CONTAINER` with its name or ID. |
| `docker system df` | Show Docker disk usage. |

References: [Git tutorial](https://git-scm.com/docs/gittutorial) and [Docker Compose up](https://docs.docker.com/reference/cli/docker/compose/up/).
