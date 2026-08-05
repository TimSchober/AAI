"""
Flask application factory for the Job Application Agent backend.

Exposes the agents from ./agents and the tool catalogue of the MCP server in
./mcp_server over plain HTTP/JSON:

  GET    /health                                    liveness
  GET    /ready                                     dependency readiness
  GET    /api/agents                                registered agents
  POST   /api/agents/<id>/chat                      one agent turn
  POST   /api/agents/<id>/chat/stream               same, as SSE updates
  GET    /api/agents/<id>/threads/<thread_id>       conversation history
  DELETE /api/agents/<id>/threads/<thread_id>       forget a conversation
  GET    /api/mcp/tools                             MCP tool catalogue
  POST   /api/mcp/tools/<name>/call                 invoke one MCP tool
"""

from __future__ import annotations

import logging
from typing import Any

import httpx
from flask import Flask, jsonify

from config import AGENT_TIMEOUT, BACKEND_CORS_ORIGINS, BACKEND_HOST, BACKEND_PORT
from backend.routes import agents_bp, health_bp, mcp_bp
from backend.runtime import AsyncRuntime
from backend.services import AgentNotFound, AgentService, MCPService, ToolNotFound

log = logging.getLogger(__name__)


def create_app() -> Flask:
    app = Flask(__name__)
    app.config["JSON_SORT_KEYS"] = False

    runtime = AsyncRuntime()
    app.extensions["async_runtime"] = runtime
    app.extensions["agent_service"] = AgentService(runtime, timeout=AGENT_TIMEOUT)
    app.extensions["mcp_service"] = MCPService(runtime, timeout=AGENT_TIMEOUT)

    app.register_blueprint(health_bp)
    app.register_blueprint(agents_bp)
    app.register_blueprint(mcp_bp)

    _register_cors(app)
    _register_error_handlers(app)
    return app


def _register_cors(app: Flask) -> None:
    """Minimal CORS so a browser front-end can call the API directly."""
    origins = BACKEND_CORS_ORIGINS

    @app.after_request
    def add_cors_headers(response: Any) -> Any:
        response.headers.setdefault("Access-Control-Allow-Origin", origins)
        response.headers.setdefault(
            "Access-Control-Allow-Headers", "Content-Type, Authorization"
        )
        response.headers.setdefault(
            "Access-Control-Allow-Methods", "GET, POST, DELETE, OPTIONS"
        )
        return response

    @app.route("/<path:_any>", methods=["OPTIONS"])
    def preflight(_any: str) -> Any:
        return ("", 204)


def _register_error_handlers(app: Flask) -> None:
    @app.errorhandler(AgentNotFound)
    def unknown_agent(exc: AgentNotFound) -> Any:
        return jsonify({"error": f"unknown agent '{exc.args[0]}'"}), 404

    @app.errorhandler(ToolNotFound)
    def unknown_tool(exc: ToolNotFound) -> Any:
        return jsonify({"error": f"unknown MCP tool '{exc.args[0]}'"}), 404

    @app.errorhandler(TimeoutError)
    def timed_out(exc: TimeoutError) -> Any:
        return jsonify({"error": "the agent took too long", "detail": str(exc)}), 504

    @app.errorhandler(httpx.HTTPError)
    def upstream_error(exc: httpx.HTTPError) -> Any:
        log.warning("upstream call failed: %s", exc)
        return jsonify({"error": "upstream service failed", "detail": str(exc)}), 502

    @app.errorhandler(404)
    def not_found(_exc: Any) -> Any:
        return jsonify({"error": "not found"}), 404

    @app.errorhandler(Exception)
    def unhandled(exc: Exception) -> Any:
        # The LLM SDK wraps connection failures in its own exception types, so
        # unwrap the chain instead of matching on provider-specific classes.
        if _is_connection_error(exc):
            log.warning("dependency unreachable: %s", exc)
            return (
                jsonify(
                    {
                        "error": "a required service is unreachable",
                        "detail": str(exc),
                        "hint": "check /ready for which dependency is down",
                    }
                ),
                503,
            )
        log.exception("unhandled error")
        return jsonify({"error": "internal server error", "detail": str(exc)}), 500


def _is_connection_error(exc: BaseException) -> bool:
    seen: set[int] = set()
    current: BaseException | None = exc
    while current is not None and id(current) not in seen:
        seen.add(id(current))
        if isinstance(current, (httpx.ConnectError, httpx.ConnectTimeout, ConnectionError)):
            return True
        current = current.__cause__ or current.__context__
    return False


def main() -> None:
    logging.basicConfig(level=logging.INFO)
    create_app().run(host=BACKEND_HOST, port=BACKEND_PORT, threaded=True)


if __name__ == "__main__":
    main()
