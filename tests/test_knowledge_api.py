"""
Tests for the knowledge-base upload endpoint.
"""

from __future__ import annotations

import json
from io import BytesIO
from typing import Any, Iterator

import pytest
from flask import Flask
from flask.testing import FlaskClient

import config
from backend.app import create_app


def as_blocks(payload: dict[str, Any]) -> list[dict[str, str]]:
    return [{"type": "text", "text": json.dumps(payload), "id": "lc_1"}]


class StubMCP:
    """Records the tool calls the route makes and answers like MCP does."""

    def __init__(self) -> None:
        self.calls: list[tuple[str, dict[str, Any]]] = []
        self.fail_with: Exception | None = None

    def call_tool(self, name: str, arguments: dict[str, Any]) -> dict[str, Any]:
        self.calls.append((name, arguments))
        if self.fail_with is not None and name != "list_knowledge":
            raise self.fail_with
        if name == "list_knowledge":
            return {"tool": name, "result": as_blocks({"lebenslauf": 3, "anhang": 1})}
        if name == "ingest_file":
            return {
                "tool": name,
                "result": as_blocks(
                    {"source": "ab12_Lebenslauf.md", "type": "lebenslauf", "stored": 2}
                ),
            }
        if name == "ingest_image":
            return {"tool": name, "result": as_blocks({"source": "cd34_bild.png", "stored": 1})}
        raise AssertionError(f"unexpected tool {name}")

    def list_tools(self, refresh: bool = False) -> dict[str, Any]:
        return {"count": 0, "tools": []}


@pytest.fixture
def mcp() -> StubMCP:
    return StubMCP()


@pytest.fixture
def app(mcp: StubMCP) -> Iterator[Flask]:
    application = create_app()
    application.config["TESTING"] = True
    application.extensions["mcp_service"] = mcp
    yield application
    application.extensions["async_runtime"].shutdown()


@pytest.fixture
def client(app: Flask) -> FlaskClient:
    return app.test_client()


def part(name: str, mime: str, data: bytes = b"content") -> tuple:
    return (BytesIO(data), name, mime)


def test_overview_reports_what_is_stored_and_what_is_accepted(
    client: FlaskClient,
) -> None:
    payload = client.get("/api/knowledge").get_json()

    assert payload["counts"] == {"lebenslauf": 3, "anhang": 1}
    assert payload["total"] == 4
    assert "lebenslauf" in payload["doc_types"]
    assert ".pdf" in payload["accepts"]["documents"]
    assert payload["accepts"]["max_mb"] == config.MAX_UPLOAD_MB


def test_overview_survives_an_unreachable_mcp_server(
    client: FlaskClient, mcp: StubMCP
) -> None:
    """The page must still render its form when the store is down."""

    def boom(name: str, arguments: dict[str, Any]) -> dict[str, Any]:
        raise ConnectionError("mcp refused the connection")

    mcp.call_tool = boom

    response = client.get("/api/knowledge")

    assert response.status_code == 200
    payload = response.get_json()
    assert payload["counts"] == {}
    assert "refused" in payload["unavailable"]
    assert payload["doc_types"]


def test_a_document_goes_to_ingest_file(client: FlaskClient, mcp: StubMCP) -> None:
    response = client.post(
        "/api/knowledge/documents",
        content_type="multipart/form-data",
        data={"files": part("Lebenslauf.md", "text/markdown", b"# Lebenslauf")},
    )

    assert response.status_code == 200
    result = response.get_json()["results"][0]
    assert result == {
        "ok": True,
        "filename": "Lebenslauf.md",
        "kind": "document",
        "doc_type": "lebenslauf",
        "stored": 2,
        "source": "ab12_Lebenslauf.md",
    }

    tool, args = next(c for c in mcp.calls if c[0] == "ingest_file")
    assert args["filename"] == "Lebenslauf.md"
    assert args["doc_type"] == ""  # empty: the MCP server infers it from the name


def test_an_image_goes_to_ingest_image_with_its_caption(
    client: FlaskClient, mcp: StubMCP
) -> None:
    client.post(
        "/api/knowledge/documents",
        content_type="multipart/form-data",
        data={
            "files": part("bild.png", "image/png", b"\x89PNG"),
            "caption": "Notenübersicht",
        },
    )

    _, args = next(c for c in mcp.calls if c[0] == "ingest_image")
    assert args["mime_type"] == "image/png"
    assert args["caption"] == "Notenübersicht"
    assert "ingest_file" not in [c[0] for c in mcp.calls]


def test_an_explicit_doc_type_is_passed_through(client: FlaskClient, mcp: StubMCP) -> None:
    client.post(
        "/api/knowledge/documents",
        content_type="multipart/form-data",
        data={"files": part("scan.pdf", "application/pdf"), "doc_type": "zeugnis"},
    )

    _, args = next(c for c in mcp.calls if c[0] == "ingest_file")
    assert args["doc_type"] == "zeugnis"


def test_an_unknown_doc_type_is_refused(client: FlaskClient, mcp: StubMCP) -> None:
    response = client.post(
        "/api/knowledge/documents",
        content_type="multipart/form-data",
        data={"files": part("a.md", "text/markdown"), "doc_type": "quatsch"},
    )

    assert response.status_code == 400
    assert "quatsch" in response.get_json()["error"]
    assert mcp.calls == []


def test_one_bad_file_does_not_sink_the_others(client: FlaskClient) -> None:
    response = client.post(
        "/api/knowledge/documents",
        content_type="multipart/form-data",
        data={
            "files": [
                part("Lebenslauf.md", "text/markdown"),
                part("programm.exe", "application/octet-stream"),
                part("leer.txt", "text/plain", b""),
            ]
        },
    )

    assert response.status_code == 200
    results = {r["filename"]: r for r in response.get_json()["results"]}
    assert results["Lebenslauf.md"]["ok"] is True
    assert results["programm.exe"]["ok"] is False
    assert "nicht unterstützt" in results["programm.exe"]["error"]
    assert results["leer.txt"]["error"] == "die Datei ist leer"
    assert response.get_json()["stored"] == 2


def test_only_unusable_files_answer_415(client: FlaskClient) -> None:
    response = client.post(
        "/api/knowledge/documents",
        content_type="multipart/form-data",
        data={"files": part("programm.exe", "application/octet-stream")},
    )

    assert response.status_code == 415
    assert response.get_json()["results"][0]["ok"] is False


def test_a_file_over_the_limit_is_rejected_before_it_reaches_mcp(
    client: FlaskClient, mcp: StubMCP, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(config, "MAX_UPLOAD_MB", 1)

    response = client.post(
        "/api/knowledge/documents",
        content_type="multipart/form-data",
        data={"files": part("gross.txt", "text/plain", b"x" * (1024 * 1024 + 1))},
    )

    assert response.status_code == 415
    assert "Limit von 1 MB" in response.get_json()["results"][0]["error"]
    assert [c[0] for c in mcp.calls] == ["list_knowledge"]


def test_a_failing_mcp_tool_is_reported_per_file(
    client: FlaskClient, mcp: StubMCP
) -> None:
    mcp.fail_with = RuntimeError("chroma is down")

    response = client.post(
        "/api/knowledge/documents",
        content_type="multipart/form-data",
        data={"files": part("Lebenslauf.md", "text/markdown")},
    )

    assert response.status_code == 415
    assert "chroma is down" in response.get_json()["results"][0]["error"]


@pytest.mark.parametrize(
    "raw",
    [
        [{"type": "text", "text": '{"stored": 2}', "id": "lc_1"}],
        [{"type": "text", "text": '{"stored":'}, {"type": "text", "text": " 2}"}],
        '{"stored": 2}',
        {"stored": 2},
    ],
    ids=["content-blocks", "split-blocks", "json-string", "plain-dict"],
)
def test_every_shape_an_mcp_tool_may_return_is_decoded(raw: Any) -> None:
    from backend.routes.knowledge import _unwrap

    assert _unwrap(raw) == {"stored": 2}


def test_a_non_json_tool_result_is_passed_through_as_text() -> None:
    from backend.routes.knowledge import _unwrap

    assert _unwrap([{"type": "text", "text": "chroma is down"}]) == "chroma is down"


def test_an_empty_request_is_a_bad_request(client: FlaskClient) -> None:
    response = client.post(
        "/api/knowledge/documents", content_type="multipart/form-data", data={}
    )

    assert response.status_code == 400
    assert "no files" in response.get_json()["error"]
