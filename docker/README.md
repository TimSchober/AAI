# Docker

Four images, all built from the **repository root** as context.

| Service    | Dockerfile          | Port   | What it is                                        |
| ---------- | ------------------- | ------ | ------------------------------------------------- |
| `backend`  | `Dockerfile.backend`| 5000   | Flask API + the agents from `./agents`            |
| `mcp`      | `Dockerfile.mcp`    | 8000   | MCP server — the shared tool layer                |
| `rag`      | `Dockerfile.rag`    | 8200   | ChromaDB vector store (the knowledge base)        |
| `jobsuche` | `Dockerfile.jobsuche`| 8100  | HTTP wrapper around the Arbeitsagentur job board  |

## Full stack

```bash
cp .env.example .env      # optional, compose has defaults for everything
docker compose up --build
```

Then: <http://localhost:5000/api/agents> and <http://localhost:5000/api/mcp/tools>.

Interactive CLI against the same stack:

```bash
docker compose run --rm cli
```

## Individual builds

```bash
docker build -f docker/Dockerfile.backend  -t aai-backend  .
docker build -f docker/Dockerfile.mcp      -t aai-mcp      .
docker build -f docker/Dockerfile.rag      -t aai-rag      .
docker build -f docker/Dockerfile.jobsuche -t aai-jobsuche .
```

## How the services find each other

Compose sets these; running containers by hand means setting them yourself.

| Variable               | Value in compose        | Effect                                            |
| ---------------------- | ----------------------- | ------------------------------------------------- |
| `CHROMA_HOST`          | `rag`                   | RAG store switches from embedded to server mode   |
| `JOBSUCHE_SERVICE_URL` | `http://jobsuche:8100`  | MCP routes job board calls through the service    |
| `MCP_URL`              | `http://mcp:8000/mcp`   | Backend loads its tools from the MCP server       |
| `OLLAMA_BASE_URL`      | `host.docker.internal`  | Reaches Ollama on the host                        |

Leaving `CHROMA_HOST` and `JOBSUCHE_SERVICE_URL` empty restores the original
in-process behaviour, which is what a plain `python -m mcp_server` still does.

## Notes

- **Ollama is not containerised.** It normally runs on the host, often with GPU
  access. `extra_hosts: host-gateway` makes `host.docker.internal` work on Linux
  too. To use a remote Ollama, set `OLLAMA_BASE_URL` in `.env`.
- **The `mcp` image is large (~2–3 GB).** `sentence-transformers` pulls in
  torch. Embeddings are computed by the *client*, not by Chroma, so the
  embedding model is baked into this image at build time to avoid downloading
  it on every start.
- **`rag` is plain storage.** It holds vectors and metadata; it runs no model.
- **The knowledge base persists** in the `rag-data` volume. `docker compose down
  -v` deletes it.
- **Ingesting documents:** put files in `./ChromaDB/docs` (mounted read-only
  into the MCP container at `/app/docs`) and call the `ingest_documents` tool:
  ```bash
  curl -X POST localhost:5000/api/mcp/tools/ingest_documents/call \
    -H 'Content-Type: application/json' -d '{"arguments": {}}'
  ```
- **The backend runs one gunicorn worker** on purpose — conversation state is
  in-memory. Scaling out needs a shared checkpointer (e.g. Postgres) first.
