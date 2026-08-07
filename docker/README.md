# Docker

Five images, all built from the **repository root** as context.

| Service    | Dockerfile          | Port   | What it is                                        |
| ---------- | ------------------- | ------ | ------------------------------------------------- |
| `frontend` | `Dockerfile.frontend`| 8080  | Vue chat UI, served by nginx which proxies `/api` |
| `backend`  | `Dockerfile.backend`| 5000   | Flask API + the agents from `./agents`            |
| `mcp`      | `Dockerfile.mcp`    | 8000   | MCP server, the shared tool layer                |
| `rag`      | `Dockerfile.rag`    | 8200   | ChromaDB vector store          |
| `jobsuche` | `Dockerfile.jobsuche`| 8100  | HTTP wrapper around the Arbeitsagentur job board  |

## Full stack

```bash
cp .env.example .env
docker compose up --build
```

.env needs to be adjusted, depending on the secrets.

Then the chat UI is on <http://localhost:8080>, and the API directly on
<http://localhost:5000/api/agents> and <http://localhost:5000/api/mcp/tools>.

## Individual builds

```bash
docker build -f docker/Dockerfile.frontend -t aai-frontend .
docker build -f docker/Dockerfile.backend  -t aai-backend  .
docker build -f docker/Dockerfile.mcp      -t aai-mcp      .
docker build -f docker/Dockerfile.rag      -t aai-rag      .
docker build -f docker/Dockerfile.jobsuche -t aai-jobsuche .
```

## Published images (CI)

Every push to `main` runs `.github/workflows/docker-publish.yml`, which builds
all five images for `linux/amd64` and pushes them to a single Docker Hub
repository, `tims1014/repo_for_aai_lecture`. The service name is the tag
prefix, and each build also gets an immutable commit-pinned tag:

```
tims1014/repo_for_aai_lecture:backend
tims1014/repo_for_aai_lecture:backend-<sha>
```

To run the stack from the published images instead of building locally,
override the `image:` keys — for example:

```bash
docker pull tims1014/repo_for_aai_lecture:backend
docker pull tims1014/repo_for_aai_lecture:mcp
docker pull tims1014/repo_for_aai_lecture:frontend
docker pull tims1014/repo_for_aai_lecture:rag
docker pull tims1014/repo_for_aai_lecture:jobsuche

docker tag  tims1014/repo_for_aai_lecture:backend aai-backend
docker tag  tims1014/repo_for_aai_lecture:mcp aai-mcp
docker tag  tims1014/repo_for_aai_lecture:frontend aai-frontend
docker tag  tims1014/repo_for_aai_lecture:rag aai-rag
docker tag  tims1014/repo_for_aai_lecture:jobsuche aai-jobsuche
```

## How the services find each other

Compose sets these; running containers by hand means setting them yourself.

| Variable               | Value in compose        | Effect                                            |
| ---------------------- | ----------------------- | ------------------------------------------------- |
| `CHROMA_HOST`          | `rag`                   | RAG store switches from embedded to server mode   |
| `JOBSUCHE_SERVICE_URL` | `http://jobsuche:8100`  | MCP routes job board calls through the service    |
| `MCP_URL`              | `http://mcp:8000/mcp`   | Backend loads its tools from the MCP server       |
| `OLLAMA_BASE_URL`      | `host.docker.internal`  | Reaches Ollama on the host                        |
| `BACKEND_ORIGIN`       | `http://backend:5000`   | Where nginx proxies the front-end's `/api` calls  |
| `BRAVE_API_KEY`        | from `.env`, empty      | adds web search to the company research           |

## Important!

### Ollama is not containerised
It normally runs on the host. To use a remote Ollama, set `OLLAMA_BASE_URL` in `.env`.

### The knowledge base persists in the `rag-data` volume.
`docker compose down -v` deletes it!
