"""
Integration tests for the Flask backend.
"""

from __future__ import annotations

import base64
from typing import Iterator

import pytest
from flask import Flask
from flask.testing import FlaskClient

from backend.app import create_app

PNG_DATA_URL = "data:image/png;base64," + base64.b64encode(b"pixels").decode("ascii")


@pytest.fixture
def app() -> Iterator[Flask]:
    application = create_app()
    application.config["TESTING"] = True
    yield application
    application.extensions["async_runtime"].shutdown()


@pytest.fixture
def client(app: Flask) -> FlaskClient:
    return app.test_client()


def test_health_never_touches_a_dependency(client: FlaskClient) -> None:
    response = client.get("/health")

    assert response.status_code == 200
    assert response.get_json() == {"status": "ok", "service": "agent-backend"}


def test_agents_are_listed_with_cors_headers(client: FlaskClient) -> None:
    response = client.get("/api/agents")

    assert response.status_code == 200
    payload = response.get_json()
    assert payload["count"] == len(payload["agents"])
    assert {a["id"] for a in payload["agents"]} == {"job_search", "company_research"}
    assert all(a["name"] and a["description"] for a in payload["agents"])
    # The Vue frontend calls the API cross-origin.
    assert response.headers["Access-Control-Allow-Origin"]


@pytest.mark.parametrize("path", ["/api/agents/job_search/chat", "/api/anything"])
def test_preflight_is_answered_for_any_path(client: FlaskClient, path: str) -> None:
    response = client.options(path)

    assert response.status_code == 204
    assert "POST" in response.headers["Access-Control-Allow-Methods"]
    assert response.headers["Access-Control-Allow-Origin"]


def test_chat_without_message_or_image_is_a_bad_request(client: FlaskClient) -> None:
    response = client.post("/api/agents/job_search/chat", json={"message": "   "})

    assert response.status_code == 400
    assert "message" in response.get_json()["error"]


def test_unknown_agent_is_reported_as_not_found(client: FlaskClient) -> None:
    response = client.post("/api/agents/does_not_exist/chat", json={"message": "hallo"})

    assert response.status_code == 404
    assert response.get_json() == {"error": "unknown agent 'does_not_exist'"}


def test_unknown_route_answers_json_not_html(client: FlaskClient) -> None:
    response = client.get("/api/nope")

    assert response.status_code == 404
    assert response.is_json
    assert response.get_json() == {"error": "not found"}


def test_a_rejected_attachment_becomes_its_own_http_status(
    client: FlaskClient,
) -> None:
    """AttachmentError carries the status through the app-wide error handler."""
    response = client.post(
        "/api/agents/job_search/chat",
        json={
            "message": "Was steht hier?",
            "images": ["data:application/pdf;base64,QQ=="],
        },
    )

    assert response.status_code == 415
    assert "unsupported image type" in response.get_json()["error"]


def test_a_body_over_the_flask_limit_is_rejected_before_the_route(
    app: Flask, client: FlaskClient
) -> None:
    oversized = "x" * (app.config["MAX_CONTENT_LENGTH"] + 1)

    response = client.post(
        "/api/agents/job_search/chat",
        data=oversized,
        content_type="application/json",
    )

    assert response.status_code == 413
    assert "MB" in response.get_json()["error"]
