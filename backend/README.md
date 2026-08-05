# Backend API

Flask HTTP layer over the agents in [`../agents`](../agents) and the MCP server
in [`../mcp_server`](../mcp_server).

## Run

```bash
python -m backend                      # dev server
gunicorn --workers 1 --threads 8 --timeout 600 backend.wsgi:app   # production
```

The MCP server must be running first (`python -m mcp_server`), because the
agent's tools are loaded from it.

> Use a **single** gunicorn worker. Conversation state (the LangGraph
> `MemorySaver`) and the agent event loop live in process memory, so a second
> worker would hold a different set of conversations.

## Endpoints

| Method   | Path                                        | Purpose                                |
| -------- | ------------------------------------------- | -------------------------------------- |
| `GET`    | `/health`                                   | Liveness, touches nothing downstream   |
| `GET`    | `/ready`                                    | Ollama + MCP reachability (503 if not) |
| `GET`    | `/api/agents`                               | Registered agents                      |
| `POST`   | `/api/agents/<id>/chat`                     | One agent turn, full reply             |
| `POST`   | `/api/agents/<id>/chat/stream`              | Same turn as SSE updates               |
| `GET`    | `/api/agents/<id>/threads/<thread_id>`      | Conversation history                   |
| `DELETE` | `/api/agents/<id>/threads/<thread_id>`      | Forget a conversation                  |
| `GET`    | `/api/mcp/tools`                            | MCP tool catalogue (`?refresh=1`)      |
| `POST`   | `/api/mcp/tools/<name>/call`                | Invoke a single MCP tool               |

### Chat

`thread_id` is optional; omitting it starts a new conversation and the
generated id comes back in the response. Reuse it to continue.

```bash
curl -X POST localhost:5000/api/agents/job_search/chat \
  -H 'Content-Type: application/json' \
  -d '{"message": "Ich suche eine Stelle als Softwareentwickler in Berlin, Vollzeit.",
       "thread_id": "demo"}'
```

```json
{
  "agent": "job_search",
  "thread_id": "demo",
  "reply": "Hier sind die passenden Vollzeit-Stellen …",
  "tool_calls": [
    {"name": "search_jobs", "args": {"was": "Softwareentwickler", "wo": "Berlin", "arbeitszeit": "vz"}}
  ]
}
```

### Streaming

Same body, `text/event-stream` response. Each frame is one JSON object:
`{"type": "start"}`, then `{"type": "message", "node": …, "role": …, "content": …}`
per graph update, then `{"type": "end"}`. Failures arrive as
`{"type": "error", "error": …}` rather than a broken connection.

### MCP tools

```bash
curl localhost:5000/api/mcp/tools
curl -X POST localhost:5000/api/mcp/tools/query_knowledge/call \
  -H 'Content-Type: application/json' \
  -d '{"arguments": {"query": "Python", "n_results": 3}}'
```

The catalogue is cached after the first load; `?refresh=1` re-reads it from the
MCP server.

## Layout

| File                | Role                                                        |
| ------------------- | ----------------------------------------------------------- |
| `app.py`            | App factory, CORS, error handlers                            |
| `runtime.py`        | Background asyncio loop bridging sync Flask to async agents  |
| `services.py`       | Agent registry, conversation handling, MCP tool access       |
| `serialization.py`  | LangChain messages / tools → JSON                            |
| `routes/`           | Blueprints per area                                          |

## Adding an agent

Add an `AgentSpec` to `AGENT_SPECS` in `services.py` pointing at an async
builder that takes a checkpointer, the way
`agents/job_search_agent.py:build_job_search_agent` does. It is then served on
every `/api/agents/<id>/…` route automatically.
