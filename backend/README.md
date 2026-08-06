# Backend API

Flask HTTP layer over the agents in [`../agents`](../agents) and the MCP server
in [`../mcp_server`](../mcp_server).

## Run

For dev:
```bash
python -m backend
```

For prod:
```bash
gunicorn --workers 1 --threads 8 --timeout 600 backend.wsgi:app
```

The MCP server must be running first! By:

```bash
python -m mcp_server
```

## Endpoints

| Method   | Path                                        | Purpose                                |
| -------- | ------------------------------------------- | -------------------------------------- |
| `GET`    | `/health`                                   | Liveness, touches nothing downstream   |
| `GET`    | `/ready`                                    | Ollama + MCP reachability              |
| `GET`    | `/api/agents`                               | Registered agents                      |
| `POST`   | `/api/agents/<id>/chat`                     | One agent turn, full reply             |
| `POST`   | `/api/agents/<id>/chat/stream`              | Same turn as SSE updates               |
| `GET`    | `/api/agents/<id>/threads/<thread_id>`      | Conversation history                   |
| `DELETE` | `/api/agents/<id>/threads/<thread_id>`      | Forget a conversation                  |
| `GET`    | `/api/mcp/tools`                            | MCP tool catalogue                     |
| `POST`   | `/api/mcp/tools/<name>/call`                | Invoke a single MCP tool               |

### Agents

| `<id>`             | Agent                                                          |
| ------------------ | -------------------------------------------------------------- |
| `job_search`       | Searches the Arbeitsagentur job board                          |
| `company_research` | Researches the employer behind a found offer                   |

### Chat

`thread_id` is optional. If not send, it starts a new conversation and the
generated id comes back in the response.

```bash
curl -X POST localhost:5000/api/agents/job_search/chat \
  -H 'Content-Type: application/json' \
  -d '{"message": "Ich suche eine Stelle als Softwareentwickler in Berlin, Vollzeit.",
       "thread_id": "demo"}'
```

### Images

Both chat endpoints also accept `multipart/form-data` with `message`,
`thread_id` and any number of `images` parts:

```bash
curl -X POST localhost:5000/api/agents/job_search/chat \
  -F 'message=Was steht in diesem Zeugnis?' \
  -F 'thread_id=demo' \
  -F 'images=@zeugnis.png'
```

An attached image goes two ways:

1. It is filed into the knowledge base through the MCP tool `ingest_image`.
2. It is handed to the model as an OpenAI-style `image_url` block, which
   Ollama's compatible API accepts. For this the vision model, `qwen2.5vl`, is used.

### MCP tools

```bash
curl localhost:5000/api/mcp/tools
curl -X POST localhost:5000/api/mcp/tools/query_knowledge/call \
  -H 'Content-Type: application/json' \
  -d '{"arguments": {"query": "Python", "n_results": 3}}'

curl -X POST localhost:5000/api/mcp/tools/research_company/call \
  -H 'Content-Type: application/json' \
  -d '{"arguments": {"name": "TRUMPF SE + Co. KG", "location": "Ditzingen"}}'
```

Although we tested it several times with Postman, sometimes an (yet) unknown bug still occurs.
