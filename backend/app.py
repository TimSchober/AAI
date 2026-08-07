"""
Flask application factory for the Job Application Agent backend.

Exposes the agents from ./agents and the tool catalogue of the MCP server in
./mcp_server over plain HTTP/JSON.

  GET    /health                                    liveness
  GET    /ready                                     dependency readiness
  GET    /api/agents                                registered agents
  POST   /api/agents/<id>/chat                      one agent turn
  POST   /api/agents/<id>/chat/stream               same, as SSE updates
  GET    /api/agents/<id>/threads/<thread_id>       conversation history
  DELETE /api/agents/<id>/threads/<thread_id>       forget a conversation
  GET    /api/mcp/tools                             MCP tool catalogue
  POST   /api/mcp/tools/<name>/call                 invoke one MCP tool
  GET    /api/knowledge                             what the RAG store holds
  POST   /api/knowledge/documents                   upload files into the store
  GET    /api/settings                              adjustable configuration
  PUT    /api/settings                              change it at runtime

The two chat endpoints take JSON or multipart/form-data; the latter is how
images reach the agent, thats for feeding the Lebenslauf etc.
"""

from __future__ import annotations

import logging
from typing import Any

import httpx
from flask import Flask, jsonify, request

import config
from backend.attachments import AttachmentError
from backend.errors import is_connection_error
from backend.routes import agents_bp, health_bp, knowledge_bp, mcp_bp, settings_bp
from backend.runtime import AsyncRuntime
from backend.services import AgentNotFound, AgentService, MCPService, ToolNotFound
from backend.settings import SettingsError

log = logging.getLogger(__name__)


def create_app() -> Flask:
    app = Flask(__name__)
    app.config["JSON_SORT_KEYS"] = False
    app.config["MAX_CONTENT_LENGTH"] = (config.MAX_UPLOAD_MB + 1) * 1024 * 1024

    runtime = AsyncRuntime()
    mcp_service = MCPService(runtime, timeout=config.AGENT_TIMEOUT)
    app.extensions["async_runtime"] = runtime
    app.extensions["mcp_service"] = mcp_service
    app.extensions["agent_service"] = AgentService(
        runtime, timeout=config.AGENT_TIMEOUT, mcp=mcp_service
    )

    app.register_blueprint(health_bp)
    app.register_blueprint(agents_bp)
    app.register_blueprint(mcp_bp)
    app.register_blueprint(knowledge_bp)
    app.register_blueprint(settings_bp)

    _register_cors(app)
    _register_error_handlers(app)
    return app


def _register_cors(app: Flask) -> None:
    """Minimal CORS so a browser front-end can call the API directly."""

    @app.after_request
    def add_cors_headers(response: Any) -> Any:
        response.headers.setdefault(
            "Access-Control-Allow-Origin", config.BACKEND_CORS_ORIGINS
        )
        response.headers.setdefault(
            "Access-Control-Allow-Headers", "Content-Type, Authorization"
        )
        response.headers.setdefault(
            "Access-Control-Allow-Methods", "GET, POST, DELETE, OPTIONS"
        )
        return response

    @app.before_request
    def preflight() -> Any:
        """
        Answer every CORS preflight before routing matters.

        A catch-all OPTIONS *route* would also claim unknown paths, so a plain
        GET on one would fail with 405 instead of 404.
        """
        if request.method == "OPTIONS":
            return ("", 204)
        return None


def _register_error_handlers(app: Flask) -> None:
    @app.errorhandler(AttachmentError)
    def bad_attachment(exc: AttachmentError) -> Any:
        return jsonify({"error": str(exc)}), exc.status

    @app.errorhandler(SettingsError)
    def bad_setting(exc: SettingsError) -> Any:
        return jsonify({"error": str(exc)}), exc.status

    @app.errorhandler(413)
    def too_large(_exc: Any) -> Any:
        return jsonify({"error": f"request body exceeds {config.MAX_UPLOAD_MB} MB"}), 413

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
        if is_connection_error(exc):
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


def main() -> None:
    logging.basicConfig(level=logging.INFO)
    create_app().run(host=config.BACKEND_HOST, port=config.BACKEND_PORT, threaded=True)


if __name__ == "__main__":
    main()
