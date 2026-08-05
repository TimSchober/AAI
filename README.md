# Job Application Agent

A multi-agent system that helps users **find jobs** and (in future) **improve
applications**. Agents share capabilities and data through a single **MCP
server**, which is the communication backbone for adding more agents later.

## Components

| Path             | What it is                                                    |
| ---------------- | ------------------------------------------------------------- |
| `agents/`        | The LangGraph agents                                           |
| `backend/`       | Flask API exposing the agents and the MCP tools over HTTP      |
| `mcp_server/`    | MCP server — the shared tool layer                             |
| `core_functions/`| Job board client and the ChromaDB RAG store                    |
| `services/`      | The jobsuche API microservice                                  |
| `docker/`        | Dockerfiles for all four services                              |

Two deployment shapes, same code:

- **Local** — everything in-process: the RAG store is an embedded on-disk
  ChromaDB and the MCP server calls the Arbeitsagentur API directly.
- **Docker** — each piece is its own container. Setting `CHROMA_HOST` and
  `JOBSUCHE_SERVICE_URL` is what switches the code over; unset, it behaves
  exactly as it does locally.

## Quick start with Docker

```bash
docker compose up --build
curl localhost:5000/api/agents
```

See [`docker/README.md`](docker/README.md). Ollama still runs on the host.

## Setup

### Setup python venv

When python is installed on your machine use this command to create a virtual environment:

```bash
python -m venv ./venv
```

Then activate the venv by:

```bash
source ./venv/bin/activate
```

Then install the required packages:

```bash
pip install -r requirements.txt
```

### Setup Environment Variables

Setup env vars by copying the example env vile like this:

```bash
cp .env.example .env
```

Then edit the values in the .env file.

### Setup Ollama

Make sure Ollama is running and the model is pulled:

```bash
ollama serve
ollama pull qwen3.5:4b
```

Ollama needs to be running on port 11434, otherwise it can be adjusted in .env file.

## Run

If you want you can put files (.md) inside the ./ChromaDB/docs folder and then run the following command to insert the files to the RAG DB:

```bash
python -m ingest
```

The agent and the MCP server are separate processes.
The MCP server needs to run by running:

```bash
python -m mcp_server
```

After that the agents can be started by running:

```bash
python -m main
```

### HTTP API

Instead of the CLI, the agents can be reached over HTTP. With the MCP server
running, start the Flask backend:

```bash
python -m backend
```

```bash
curl localhost:5000/api/mcp/tools          # tools available on the MCP server
curl -X POST localhost:5000/api/agents/job_search/chat \
  -H 'Content-Type: application/json' \
  -d '{"message": "Ich suche eine Stelle als Softwareentwickler in Berlin."}'
```

Endpoint reference: [`backend/README.md`](backend/README.md).

### Jobsuche microservice (optional)

The job board can also run as its own service:

```bash
python -m services.jobsuche_api
```

Point the MCP server at it with `JOBSUCHE_SERVICE_URL=http://localhost:8100`.

## Example

> Ich suche eine Stelle als Softwareentwickler in Berlin, Vollzeit.

The agent searches the Arbeitsagentur job board, caches the offers in the RAG
store, categorizes them and presents a list. If nothing matches it returns an
empty list and suggests relaxing the preferences.
