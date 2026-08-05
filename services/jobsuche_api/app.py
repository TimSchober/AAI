"""
Jobsuche microservice: a thin HTTP wrapper around the Arbeitsagentur
Jobsuche API client.

Running the job board behind its own service keeps the upstream API key and
the rate-limited outbound traffic in one place, so the MCP server (and any
future agent) can reach the job board over plain HTTP.

Endpoints:
  GET /health              – liveness
  GET /jobs                – search offers (query params mirror the client)
  GET /jobs/<referenznummer> – full details for one offer
"""

from __future__ import annotations

import logging
from typing import Any

import httpx
from flask import Flask, jsonify, request

from config import (
    JOBSUCHE_API_URL,
    JOBSUCHE_SERVICE_HOST,
    JOBSUCHE_SERVICE_PORT,
)
from core_functions.arbeitsagentur_jobsuche_API_jobs_client import JobsucheClient

log = logging.getLogger(__name__)


def _int_arg(name: str) -> int | None:
    raw = request.args.get(name)
    if raw in (None, ""):
        return None
    try:
        return int(raw)
    except ValueError:
        return None


def _str_arg(name: str) -> str | None:
    value = request.args.get(name)
    return value or None


def create_app() -> Flask:
    app = Flask(__name__)
    client = JobsucheClient()

    @app.get("/health")
    def health() -> Any:
        return jsonify(
            {
                "status": "ok",
                "service": "jobsuche-api",
                "upstream": JOBSUCHE_API_URL,
            }
        )

    @app.get("/jobs")
    def search_jobs() -> Any:
        was = _str_arg("was")
        if not was:
            return jsonify({"error": "query parameter 'was' is required"}), 400

        zeitarbeit = request.args.get("zeitarbeit", "true").lower() != "false"
        jobs = client.search(
            was=was,
            wo=_str_arg("wo"),
            berufsfeld=_str_arg("berufsfeld"),
            page=_int_arg("page") or 1,
            size=_int_arg("size") or 10,
            umkreis=_int_arg("umkreis"),
            veroeffentlichtseit=_int_arg("veroeffentlichtseit"),
            angebotsart=_int_arg("angebotsart"),
            befristung=_str_arg("befristung"),
            arbeitszeit=_str_arg("arbeitszeit"),
            arbeitgeber=_str_arg("arbeitgeber"),
            zeitarbeit=zeitarbeit,
        )
        payload = [j.to_dict() for j in jobs]
        return jsonify({"count": len(payload), "jobs": payload})

    @app.get("/jobs/<path:referenznummer>")
    def job_details(referenznummer: str) -> Any:
        return jsonify(client.get_details(referenznummer).to_dict())

    @app.errorhandler(httpx.HTTPStatusError)
    def upstream_error(exc: httpx.HTTPStatusError) -> Any:
        log.warning("Jobsuche upstream error: %s", exc)
        return (
            jsonify(
                {
                    "error": "upstream job board returned an error",
                    "status": exc.response.status_code,
                }
            ),
            502,
        )

    @app.errorhandler(httpx.HTTPError)
    def upstream_unreachable(exc: httpx.HTTPError) -> Any:
        log.warning("Jobsuche upstream unreachable: %s", exc)
        return jsonify({"error": "job board unreachable", "detail": str(exc)}), 503

    return app


def main() -> None:
    logging.basicConfig(level=logging.INFO)
    create_app().run(host=JOBSUCHE_SERVICE_HOST, port=JOBSUCHE_SERVICE_PORT)


if __name__ == "__main__":
    main()
