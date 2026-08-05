"""
Service layer between the Flask routes and the agent / MCP internals.

Holds the lazily built agents, their shared checkpointer (so a thread_id keeps
its conversation across requests) and the cached MCP tool list.
"""

from __future__ import annotations

import threading
from dataclasses import dataclass
from typing import Any, AsyncIterator, Awaitable, Callable

from langgraph.checkpoint.memory import MemorySaver

from agents.job_search_agent import build_job_search_agent
from agents.mcp_client import load_mcp_tools
from backend.runtime import AsyncRuntime
from backend.serialization import message_to_dict, tool_to_dict


class AgentNotFound(KeyError):
    """Raised when a request names an agent that is not registered."""


class ToolNotFound(KeyError):
    """Raised when a request names an MCP tool the server does not expose."""


@dataclass(frozen=True)
class AgentSpec:
    id: str
    name: str
    description: str
    builder: Callable[[MemorySaver], Awaitable[Any]]


AGENT_SPECS: dict[str, AgentSpec] = {
    "job_search": AgentSpec(
        id="job_search",
        name="Job-Such-Agent",
        description=(
            "Sucht über die Bundesagentur für Arbeit passende Stellenangebote, "
            "speichert sie in der Wissensdatenbank und stellt sie kategorisiert dar."
        ),
        builder=build_job_search_agent,
    ),
}


class AgentService:
    """Builds agents on demand and runs turns on the shared event loop."""

    def __init__(self, runtime: AsyncRuntime, timeout: float) -> None:
        self._runtime = runtime
        self._timeout = timeout
        self._agents: dict[str, Any] = {}
        self._checkpointers: dict[str, MemorySaver] = {}
        self._lock = threading.Lock()

    @staticmethod
    def list_agents() -> list[dict[str, str]]:
        return [
            {"id": spec.id, "name": spec.name, "description": spec.description}
            for spec in AGENT_SPECS.values()
        ]

    @staticmethod
    def _spec(agent_id: str) -> AgentSpec:
        try:
            return AGENT_SPECS[agent_id]
        except KeyError as exc:
            raise AgentNotFound(agent_id) from exc

    @classmethod
    def ensure_exists(cls, agent_id: str) -> None:
        """Raise AgentNotFound early, before a streaming response starts."""
        cls._spec(agent_id)

    def _get_agent(self, agent_id: str) -> Any:
        spec = self._spec(agent_id)
        with self._lock:
            if agent_id not in self._agents:
                checkpointer = MemorySaver()
                self._checkpointers[agent_id] = checkpointer
                self._agents[agent_id] = self._runtime.run(
                    spec.builder(checkpointer), timeout=self._timeout
                )
            return self._agents[agent_id]

    @staticmethod
    def _config(thread_id: str) -> dict[str, Any]:
        return {"configurable": {"thread_id": thread_id}}

    def chat(self, agent_id: str, message: str, thread_id: str) -> dict[str, Any]:
        agent = self._get_agent(agent_id)
        result = self._runtime.run(
            agent.ainvoke(
                {"messages": [{"role": "user", "content": message}]},
                self._config(thread_id),
            ),
            timeout=self._timeout,
        )

        messages = result.get("messages", [])
        reply = messages[-1] if messages else None
        tool_calls = [
            call
            for msg in messages
            for call in getattr(msg, "tool_calls", None) or []
        ]

        return {
            "agent": agent_id,
            "thread_id": thread_id,
            "reply": message_to_dict(reply)["content"] if reply else "",
            "tool_calls": [
                {"name": c.get("name"), "args": c.get("args", {})} for c in tool_calls
            ],
        }

    def stream(
        self, agent_id: str, message: str, thread_id: str
    ) -> Any:
        """Yield {"type": ..., ...} update events for one agent turn."""
        agent = self._get_agent(agent_id)

        def make_agen() -> AsyncIterator[Any]:
            return agent.astream(
                {"messages": [{"role": "user", "content": message}]},
                self._config(thread_id),
                stream_mode="updates",
            )

        for update in self._runtime.iterate(make_agen, timeout=self._timeout):
            for node, payload in (update or {}).items():
                for msg in (payload or {}).get("messages", []) or []:
                    yield {"type": "message", "node": node, **message_to_dict(msg)}

    def history(self, agent_id: str, thread_id: str) -> dict[str, Any]:
        agent = self._get_agent(agent_id)
        snapshot = self._runtime.run(
            agent.aget_state(self._config(thread_id)), timeout=self._timeout
        )
        messages = (snapshot.values or {}).get("messages", []) if snapshot else []
        return {
            "agent": agent_id,
            "thread_id": thread_id,
            "messages": [message_to_dict(m) for m in messages],
        }

    def reset_thread(self, agent_id: str, thread_id: str) -> dict[str, Any]:
        self._spec(agent_id)
        self._get_agent(agent_id)
        checkpointer = self._checkpointers.get(agent_id)

        deleted = False
        if checkpointer is not None:
            delete = getattr(checkpointer, "adelete_thread", None)
            if delete is not None:
                self._runtime.run(delete(thread_id), timeout=self._timeout)
                deleted = True
            elif (delete_sync := getattr(checkpointer, "delete_thread", None)) is not None:
                delete_sync(thread_id)
                deleted = True

        return {"agent": agent_id, "thread_id": thread_id, "deleted": deleted}


class MCPService:
    """Exposes the MCP server's tool catalogue and lets callers invoke tools."""

    def __init__(self, runtime: AsyncRuntime, timeout: float) -> None:
        self._runtime = runtime
        self._timeout = timeout
        self._tools: list[Any] | None = None
        self._lock = threading.Lock()

    def _load(self, refresh: bool = False) -> list[Any]:
        with self._lock:
            if self._tools is None or refresh:
                self._tools = self._runtime.run(load_mcp_tools(), timeout=self._timeout)
            return self._tools

    def list_tools(self, refresh: bool = False) -> dict[str, Any]:
        tools = self._load(refresh=refresh)
        return {"count": len(tools), "tools": [tool_to_dict(t) for t in tools]}

    def call_tool(self, name: str, arguments: dict[str, Any]) -> dict[str, Any]:
        tool = next((t for t in self._load() if t.name == name), None)
        if tool is None:
            # The catalogue may be stale if the MCP server gained a tool.
            tool = next((t for t in self._load(refresh=True) if t.name == name), None)
        if tool is None:
            raise ToolNotFound(name)

        result = self._runtime.run(tool.ainvoke(arguments), timeout=self._timeout)
        return {"tool": name, "result": result}
