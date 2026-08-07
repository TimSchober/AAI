# Wichtig

Auf Moodle steht für die Semesterabgabe: Fällig: Freitag, 7. August 2026, 23:59

Da wir beide die letzten zwei Wochen im Urlaub waren, müssen wir morgen noch die README anpassen und ein paar bugs lösen.

Unsere App ist so also noch nicht final fertig. Wir bitten daher mit der finalen Bewertung des Projekts noch bis Freitag, 7. August 2026 um 23:59 zu warten.

# Job Application Agent

A multi-agent system that helps users **find jobs**, **research the employers**
behind them and (in future) **improve applications**. Agents share capabilities
and data through a single **MCP server**, which is the communication backbone for
adding more agents later.

| Agent                            | Does                                                                     |
| -------------------------------- | ------------------------------------------------------------------------ |
| `job_search` Job-Such-Agent      | Searches the Arbeitsagentur job board and caches the offers              |
| `company_research` Unternehmens-Recherche-Agent | Researches the employer behind an offer from free sources |

## Components

| Path             | What it is                                                    |
| ---------------- | ------------------------------------------------------------- |
| `agents/`        | The LangGraph agents                                           |
| `backend/`       | Flask API exposing the agents and the MCP tools over HTTP      |
| `frontend/`      | Vue 3 + TypeScript chat UI on top of the backend               |
| `mcp_server/`    | MCP server — the shared tool layer                             |
| `core_functions/`| Job board client, company research client, ChromaDB RAG store  |
| `services/`      | The jobsuche API microservice                                  |
| `docker/`        | Dockerfiles for all five services                              |

Two deployment shapes, same code:

- **Local**: everything in-process: the RAG store is an embedded on-disk
  ChromaDB and the MCP server calls the Arbeitsagentur API directly.
- **Docker**: each piece is its own container. Setting `CHROMA_HOST` and
  `JOBSUCHE_SERVICE_URL` is what switches the code over.

## Prerequisites

| For                  | You need                                                     |
| -------------------- | ------------------------------------------------------------ |
| Either route         | [Ollama](https://ollama.com) on your machine                  |
| Docker route         | Docker with the Compose plugin (`docker compose version`)     |
| Local route          | Python 3.12+ and, for the web UI, Node.js 20+                 |

### Ollama

Ollama is never containerised. Start it and pull the model **before** starting the stack (This instruction is for Linux (I tested it on ubuntu)):

```bash
ollama serve
ollama pull qwen3.5:4b
ollama pull qwen2.5vl:3b # this model is used for images.
```

Ollama needs to be accessed outside of docker, by:

```bash
sudo export OLLAMA_HOST=0.0.0.0:11434
ollama serve
```

OR:

```bash
sudo systemctl edit ollama
```

Then insert this into the file:

```
[Service]
Environment="OLLAMA_HOST=0.0.0.0:11434"
```

After that restart daemon and service:

```bash
sudo systemctl daemon-reload
sudo systemctl restart ollama
```

## Quick start with Docker

First copy the example .env file like this:

```bash
cp .env.example .env
```

If you have API keys insert the to the .env file afterwards. The example config works without editing it.

After that you can start the docker containers. docker and docker-compose need to be installed first!

```bash
docker compose up --build
```

The first build takes a while and downloads several GB, mostly for the `mcp`
image. When it is up:

- Chat UI: <http://localhost:8080>
- API: <http://localhost:5000/api/agents>
- Dependency check: <http://localhost:5000/ready> — reports whether Ollama and
  the MCP server are reachable, and it is the first place to look when the chat
  returns an error.

Stop with `Ctrl+C`, remove the containers with `docker compose down`.
The knowledge base survives in a volume. `docker compose down -v` also deletes that.

Details and per-service notes: [`docker/README.md`](docker/README.md).

## Local setup (without Docker)

### 1. Python environment

```bash
python -m venv ./venv
source ./venv/bin/activate
pip install -r requirements.txt
```

### 2. Environment variables

```bash
cp .env.example .env
```

If you have API keys insert the to the .env file afterwards. The example config works without editing it.

### 3. Start the processes

Each of these runs in its own terminal. Start the MCP server first: the backend
fetches the agent's tools from it on the first chat request, and without it that
request fails.

```bash
python -m mcp_server
python -m backend
cd frontend && npm install && npm run dev
```

Then open <http://localhost:5173>. The dev server proxies `/api` to the backend
on port 5000, so both have to run.

Instead of the web UI you can talk to the same agent on the command line:

```bash
python -m main
```

## Documents for the knowledge base

Put your own files into `ChromaDB/docs` and load them:

```bash
python -m ingest
```

Two things decide whether a file is picked up:

- **Extension** — `.md`, `.txt`, `.json`, `.pdf` or `.csv`.
- **Filename** — it must contain one of these words: `lebenslauf`, `cv`,
  `motivation`, `noten`, `notenübersicht`, `zeugnis`, `arbeitszeugnis`,
  `abschlusszeugnis`, `praeferenz`. `lebenslauf_tim.md` works,
  `dokument1.md` is skipped.

Everything else is skipped silently, so check the summary the command prints.

In Docker the same folder is mounted into the `mcp` container, and the import is
triggered through the API instead:

```bash
curl -X POST localhost:5000/api/mcp/tools/ingest_documents/call \
  -H 'Content-Type: application/json' -d '{"arguments": {}}'
```

## Web UI

The Vue front-end is a chat window over that API: a side menu for switching
areas, a message stream, and a composer that takes images.

Images attached to a message are stored in the knowledge base **and** passed to
the model. Seeing them requires a vision-capable `OLLAMA_MODEL` (see
[Prerequisites](#prerequisites)); with a text-only model the picture is filed
away but the agent cannot read it. Details:
[`frontend/README.md`](frontend/README.md).

## Tests

```bash
pip install -r requirements-dev.txt
pytest
```

The suite in [`tests/`](tests) runs offline — no Ollama, MCP server, job board or
vector store has to be up. Every outbound HTTP call is answered by an
`httpx.MockTransport`, and the backend is exercised through Flask's test client.

| Test module | Covers |
| --- | --- |
| `test_attachments.py` | Chat image uploads: data URLs and multipart parts, size/type limits, filename sanitizing |
| `test_serialization.py` | LangChain messages and MCP tools turned into the JSON the frontend consumes |
| `test_company_research_client.py` | Employer name normalization plus the profile that reaches the knowledge base |
| `test_jobsuche_client.py` | Arbeitsagentur query parameters and the mapping of both response shapes |
| `test_backend_api.py` | Flask app end to end: routes, CORS, and the error handlers with their status codes |

## Optional: tracing with Phoenix

Tracing is off unless the Phoenix packages are installed — they are not part of
`requirements.txt`, and without them `tracing.py` quietly does nothing.

```bash
pip install arize-phoenix openinference-instrumentation-openai
phoenix serve                       # UI on http://localhost:6006
```

Set `AAI_TRACING_ENABLED=false` to switch it off again without uninstalling.

## Optional: jobsuche microservice

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

The UI then offers the employers of those offers for research:

> Recherchiere bitte das Unternehmen "TRUMPF SE + Co. KG" in Ditzingen.

> Branche: Maschinenbau · gegründet 1923 · Hauptsitz Ditzingen ·
> [trumpf.com](https://www.trumpf.com/) — Quellen: wikipedia:de, wikidata, openstreetmap

# Anforderungskatalog
## Pflichtanforderungen (P)
### P1 – Echter AI Agent mit Tool-Use
### P2 – TAO-Zyklus sichtbar
### P3 – Framework-Einsatz
### P4 – Dokumentation (README)
### P5 – Git-Repository mit sinnvoller Commit-Historie

## Wahlpflichtanforderungen (W)
### W1 Multi-Agent-Setup: mind. 2 Agenten mit definierter Rollenaufteilung (Orchestrator + Subagent)
### W2 Multimodale Eingabe: mind. ein Agent verarbeitet eine nicht-textuelle Modalität als Input – z. B. Bilder, Audio, Video oder strukturierte Dateien (PDF, CSV)
### W3 RAG-Komponente: das System beantwortet Fragen über eine eigene Wissensbasis / eigene Dokumente
### W4 Agentic RAG: der Retrieval-Schritt wird vom Agenten selbst als Tool gesteuert, nicht hartcodiert
### W5 Observability: mind. eine Form von Tracing oder strukturiertem Logging ist eingebaut (z. B. Langfuse, Phoenix, strukturierte stdout-Ausgabe)
### W6 Prediction Service: der Agent / das Modell ist als HTTP-API erreichbar (z.B. FastAPI, Flask)
### W7 Containerisierung: das System startet vollständig via docker compose up (Dockerfile vorhanden)
### W8 Automatisiertes Testing: mind. 5 sinnvolle Unit- oder Integrationstests VL 10
### W9 Input-Validierung & Fehlerbehandlung: fehlerhafte oder unerwartete Eingaben werden graceful abgefangen
### W10 CI/CD-Pipeline: mind. ein automatischer Schritt bei Push (GitHub Actions, GitLab CI o. ä.)
### W11 Monitoring-Endpoint: /health-Route oder Prometheus-Metriken vorhanden
### W12 Data/Concept Drift – Reflexion (min. 1/2 Seite): Wie könnte Drift das System beeinflussen? Was würde auffallen?
### W13 Continual Learning – Konzept (min. 1/2 Seite): Wie könnte das System mit neuen Daten verbessert werden?
### W14 Responsible AI – Reflexion (min. 1/2 Seite): Welche Risiken, Biases oder Missbrauchspotenziale hat euer System?