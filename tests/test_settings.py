"""
Tests for `backend.settings` and the settings endpoints.
"""

from __future__ import annotations

from pathlib import Path
from typing import Iterator

import httpx
import pytest
from flask import Flask
from flask.testing import FlaskClient

import config
from backend import settings as settings_module
from backend.app import create_app
from backend.settings import SettingsError


@pytest.fixture
def settings_file(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Never let a test write the developer's real .env.runtime."""
    path = tmp_path / "settings.env"
    monkeypatch.setattr(config, "SETTINGS_FILE", str(path))
    return path


@pytest.fixture(autouse=True)
def restore_config(monkeypatch: pytest.MonkeyPatch) -> None:
    """
    Live updates re-bind module globals; undo that after each test.
    """
    from backend import attachments

    for setting in settings_module.CATALOGUE:
        if hasattr(config, setting.key):
            monkeypatch.setattr(config, setting.key, getattr(config, setting.key))
    monkeypatch.setattr(config, "OLLAMA_OPENAI_URL", config.OLLAMA_OPENAI_URL)
    for name in ("MAX_UPLOAD_MB", "MAX_UPLOAD_BYTES", "ALLOWED_IMAGE_TYPES"):
        monkeypatch.setattr(attachments, name, getattr(attachments, name))


@pytest.fixture
def app(settings_file: Path) -> Iterator[Flask]:
    application = create_app()
    application.config["TESTING"] = True
    yield application
    application.extensions["async_runtime"].shutdown()


@pytest.fixture
def client(app: Flask) -> FlaskClient:
    return app.test_client()


def test_catalogue_is_described_with_current_values(client: FlaskClient) -> None:
    payload = client.get("/api/settings").get_json()

    fields = {f["key"]: f for group in payload["groups"] for f in group["settings"]}
    assert fields["OLLAMA_MODEL"]["value"] == config.OLLAMA_MODEL
    assert fields["OLLAMA_MODEL"]["live"] is True
    # An MCP-owned setting can be stored but not applied by the backend.
    assert fields["EMBED_MODEL"]["live"] is False
    assert fields["EMBED_MODEL"]["service"] == "mcp"
    assert fields["COMPANY_RESEARCH_LANG"]["choices"] == ["de", "en"]


def test_secrets_are_never_handed_back(client: FlaskClient, monkeypatch) -> None:
    monkeypatch.setattr(config, "BRAVE_API_KEY", "super-secret")

    payload = client.get("/api/settings").get_json()
    field = next(
        f for group in payload["groups"] for f in group["settings"] if f["key"] == "BRAVE_API_KEY"
    )

    assert field["value"] == ""
    assert field["is_set"] is True  # the UI still learns that one is configured


def test_a_live_setting_is_applied_to_the_running_backend(
    client: FlaskClient, settings_file: Path
) -> None:
    response = client.put(
        "/api/settings",
        json={"values": {"OLLAMA_MODEL": "llama3.2:3b", "OLLAMA_BASE_URL": "http://gpu-box:11434"}},
    )

    assert response.status_code == 200
    report = response.get_json()
    assert report["applied"] == ["OLLAMA_BASE_URL", "OLLAMA_MODEL"]
    assert report["restart_required"] == []

    assert config.OLLAMA_MODEL == "llama3.2:3b"
    # The agents talk to the OpenAI-compatible path, which has to follow along.
    assert config.OLLAMA_OPENAI_URL == "http://gpu-box:11434/v1"
    assert "OLLAMA_MODEL=llama3.2:3b" in settings_file.read_text(encoding="utf-8")


def test_a_foreign_setting_is_stored_and_reported_as_needing_a_restart(
    client: FlaskClient, settings_file: Path
) -> None:
    report = client.put(
        "/api/settings", json={"values": {"EMBED_MODEL": "intfloat/multilingual-e5-small"}}
    ).get_json()

    assert report["applied"] == []
    assert report["restart_required"] == [
        {"service": "mcp", "label": "MCP-Server", "settings": ["EMBED_MODEL"]}
    ]
    assert "EMBED_MODEL=intfloat/multilingual-e5-small" in settings_file.read_text()


def test_changing_the_model_forces_the_agents_to_be_rebuilt(
    app: Flask, client: FlaskClient
) -> None:
    """Otherwise the cached agent would keep talking to the old model."""
    agent_service = app.extensions["agent_service"]
    agent_service._agents["job_search"] = object()
    app.extensions["mcp_service"]._tools = []

    client.put("/api/settings", json={"values": {"OLLAMA_MODEL": "mistral:7b"}})

    assert agent_service._agents == {}
    assert app.extensions["mcp_service"]._tools is None


def test_upload_limit_change_reaches_the_attachment_checks(
    app: Flask, client: FlaskClient
) -> None:
    from backend import attachments

    client.put("/api/settings", json={"values": {"MAX_UPLOAD_MB": "25"}})

    assert config.MAX_UPLOAD_MB == 25
    assert attachments.MAX_UPLOAD_BYTES == 25 * 1024 * 1024
    assert app.config["MAX_CONTENT_LENGTH"] == 26 * 1024 * 1024


@pytest.mark.parametrize(
    ("values", "fragment"),
    [
        ({"EVIL": "x"}, "unknown setting"),
        ({"OLLAMA_BASE_URL": "ftp://box"}, "http://"),
        ({"AGENT_TIMEOUT": "bald"}, "keine ganze Zahl"),
        ({"COMPANY_RESEARCH_TIMEOUT": "viel"}, "keine Zahl"),
        ({"COMPANY_RESEARCH_LANG": "fr"}, "erlaubt sind"),
        ({"OLLAMA_MODEL": "a\nb"}, "Zeilenumbrüche"),
        ({}, "no settings"),
    ],
)
def test_bad_input_is_rejected_before_anything_is_written(
    client: FlaskClient, settings_file: Path, values: dict, fragment: str
) -> None:
    response = client.put("/api/settings", json={"values": values})

    assert response.status_code == 400
    assert fragment in response.get_json()["error"]
    assert not settings_file.exists()


def test_writing_keeps_the_rest_of_the_file(settings_file: Path) -> None:
    settings_file.write_text(
        "# a comment\nOLLAMA_MODEL=old-model\n\nEMBED_MODEL=keep-me\n", encoding="utf-8"
    )

    settings_module.update({"OLLAMA_MODEL": "new-model", "CHROMA_COLLECTION": "neu"})

    assert settings_file.read_text(encoding="utf-8").splitlines() == [
        "# a comment",
        "OLLAMA_MODEL=new-model",
        "",
        "EMBED_MODEL=keep-me",
        "CHROMA_COLLECTION=neu",
    ]


def test_values_needing_quotes_survive_a_round_trip(settings_file: Path) -> None:
    settings_module.update({"BACKEND_CORS_ORIGINS": "http://a.test http://b.test"})

    assert 'BACKEND_CORS_ORIGINS="http://a.test http://b.test"' in settings_file.read_text()
    described = settings_module.describe()
    field = next(
        f
        for group in described["groups"]
        for f in group["settings"]
        if f["key"] == "BACKEND_CORS_ORIGINS"
    )
    assert field["overridden"] is True


def test_an_unwritable_settings_file_is_reported_instead_of_crashing(
    client: FlaskClient, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """
    What happened in Docker: the named volume was created root-owned, so the
    write raised PermissionError and the user got a bare 500.
    """
    locked = tmp_path / "locked"
    locked.mkdir(mode=0o500)
    monkeypatch.setattr(config, "SETTINGS_FILE", str(locked / "settings.env"))

    response = client.put("/api/settings", json={"values": {"OLLAMA_MODEL": "mistral:7b"}})

    assert response.status_code == 500
    error = response.get_json()["error"]
    assert "nicht beschreibbar" in error
    assert str(locked) in error
    assert config.OLLAMA_MODEL != "mistral:7b"


def test_the_page_learns_up_front_whether_it_can_save(
    client: FlaskClient, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    assert client.get("/api/settings").get_json()["writable"] is True

    locked = tmp_path / "locked"
    locked.mkdir(mode=0o500)
    monkeypatch.setattr(config, "SETTINGS_FILE", str(locked / "settings.env"))

    assert client.get("/api/settings").get_json()["writable"] is False


def test_an_unreachable_endpoint_is_saved_but_flagged(
    client: FlaskClient, settings_file: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A service may be down while it is reconfigured - warn, do not refuse."""
    monkeypatch.setattr(settings_module, "_probe", lambda url: (False, "ConnectError"))

    report = client.put(
        "/api/settings", json={"values": {"OLLAMA_BASE_URL": "http://gpu-box:11434"}}
    ).get_json()

    assert report["saved"] == ["OLLAMA_BASE_URL"]
    assert "OLLAMA_BASE_URL=http://gpu-box:11434" in settings_file.read_text()
    assert len(report["warnings"]) == 1
    assert "http://gpu-box:11434" in report["warnings"][0]
    assert "nicht erreichbar" in report["warnings"][0]


def test_a_reachable_endpoint_produces_no_warning(
    client: FlaskClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(settings_module, "_probe", lambda url: (True, ""))

    report = client.put(
        "/api/settings", json={"values": {"OLLAMA_BASE_URL": "http://gpu-box:11434"}}
    ).get_json()

    assert report["warnings"] == []


def test_localhost_from_inside_a_container_gets_the_decisive_hint(
    client: FlaskClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """
    The trap that broke a running stack: http://localhost:11434 is right on the
    host and points a container at itself.
    """
    monkeypatch.setattr(settings_module, "_probe", lambda url: (False, "ConnectError"))
    monkeypatch.setattr(settings_module, "in_container", lambda: True)

    report = client.put(
        "/api/settings", json={"values": {"OLLAMA_BASE_URL": "http://localhost:11434"}}
    ).get_json()

    assert "host.docker.internal" in report["warnings"][0]


def test_no_container_hint_for_a_normal_host(
    client: FlaskClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(settings_module, "_probe", lambda url: (False, "ConnectError"))
    monkeypatch.setattr(settings_module, "in_container", lambda: True)

    report = client.put(
        "/api/settings", json={"values": {"OLLAMA_BASE_URL": "http://192.168.1.20:11434"}}
    ).get_json()

    assert "host.docker.internal" not in report["warnings"][0]


def answer_probes_with(monkeypatch: pytest.MonkeyPatch, handler) -> None:
    """Route the probe's httpx client at a mock transport."""
    real_client = httpx.Client  # captured first, or the patch recurses
    monkeypatch.setattr(
        httpx,
        "Client",
        lambda **kwargs: real_client(transport=httpx.MockTransport(handler)),
    )


def test_the_probe_calls_the_endpoint_that_answers_a_get(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    seen: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(str(request.url))
        return httpx.Response(200)

    answer_probes_with(monkeypatch, handler)

    assert settings_module._probe("http://gpu-box:11434/api/tags") == (True, "")
    assert seen == ["http://gpu-box:11434/api/tags"]


def test_an_http_error_still_counts_as_reachable(monkeypatch: pytest.MonkeyPatch) -> None:
    """The MCP endpoint answers 405 to a plain GET; that proves it is there."""
    answer_probes_with(monkeypatch, lambda request: httpx.Response(405))

    assert settings_module._probe("http://mcp:8000/mcp")[0] is True


def test_a_refused_connection_counts_as_unreachable(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("All connection attempts failed")

    answer_probes_with(monkeypatch, handler)

    assert settings_module._probe("http://localhost:11434/api/tags") == (
        False,
        "ConnectError",
    )


def test_update_rejects_a_non_object_payload() -> None:
    with pytest.raises(SettingsError):
        settings_module.update("OLLAMA_MODEL=x")  # type: ignore[arg-type]
