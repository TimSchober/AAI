"""
Runtime-editable configuration.
"""

from __future__ import annotations

import os
import threading
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable
from urllib.parse import urlsplit

import httpx

import config

BACKEND = "backend"
MCP = "mcp"
JOBSUCHE = "jobsuche"

SERVICE_LABELS = {
    BACKEND: "Backend",
    MCP: "MCP-Server",
    JOBSUCHE: "Jobsuche-Service",
}


class SettingsError(ValueError):
    """Raised when a submitted value cannot be used; carries an HTTP status."""

    def __init__(self, message: str, status: int = 400) -> None:
        super().__init__(message)
        self.status = status


@dataclass(frozen=True)
class Setting:
    """One adjustable variable."""

    key: str
    label: str
    group: str
    service: str
    kind: str = "text"
    help: str = ""
    choices: tuple[str, ...] = ()
    live: bool = False

    @property
    def restart_required(self) -> bool:
        return not self.live


CATALOGUE: tuple[Setting, ...] = (
    Setting(
        key="OLLAMA_BASE_URL",
        label="Ollama-URL",
        group="Sprachmodell",
        service=BACKEND,
        kind="url",
        help=(
            "Adresse der Ollama-Instanz. Für ein Modell auf einem anderen "
            "Rechner z.B. http://192.168.1.20:11434."
        ),
        live=True,
    ),
    Setting(
        key="OLLAMA_MODEL",
        label="Modell",
        group="Sprachmodell",
        service=BACKEND,
        help="Name des Modells, wie es `ollama list` anzeigt, z.B. qwen3.5:4b.",
        live=True,
    ),
    Setting(
        key="OLLAMA_API_KEY",
        label="API-Key",
        group="Sprachmodell",
        service=BACKEND,
        kind="secret",
        help="Ollama selbst braucht keinen Key; nötig nur hinter einem Proxy.",
        live=True,
    ),
    Setting(
        key="MCP_URL",
        label="MCP-Server-URL",
        group="Agenten",
        service=BACKEND,
        kind="url",
        help="Vom Backend aus erreichbare Adresse des MCP-Servers samt Pfad.",
        live=True,
    ),
    Setting(
        key="AGENT_TIMEOUT",
        label="Timeout je Agentenlauf (s)",
        group="Agenten",
        service=BACKEND,
        kind="int",
        help="Nach dieser Zeit bricht ein Chat-Turn mit 504 ab.",
        live=True,
    ),
    Setting(
        key="MCP_HOST",
        label="MCP-Host (Bindung)",
        group="Agenten",
        service=MCP,
        help="Interface, auf dem der MCP-Server lauscht.",
    ),
    Setting(
        key="MCP_PORT",
        label="MCP-Port (Bindung)",
        group="Agenten",
        service=MCP,
        kind="int",
    ),
    Setting(
        key="MCP_PATH",
        label="MCP-Pfad",
        group="Agenten",
        service=MCP,
        help="Pfad des Streamable-HTTP-Endpunkts, üblicherweise /mcp.",
    ),
    Setting(
        key="MAX_UPLOAD_MB",
        label="Maximale Dateigröße (MB)",
        group="Backend",
        service=BACKEND,
        kind="int",
        help="Gilt je Datei und für alle Anhänge einer Anfrage zusammen.",
        live=True,
    ),
    Setting(
        key="ALLOWED_IMAGE_TYPES",
        label="Erlaubte Bildformate",
        group="Backend",
        service=BACKEND,
        kind="csv",
        help="Kommagetrennte MIME-Typen, z.B. image/png,image/jpeg.",
        live=True,
    ),
    Setting(
        key="BACKEND_CORS_ORIGINS",
        label="CORS-Origin",
        group="Backend",
        service=BACKEND,
        help="Erlaubte Herkunft für Browser-Anfragen; * erlaubt alle.",
        live=True,
    ),
    Setting(
        key="BACKEND_HOST",
        label="Backend-Host (Bindung)",
        group="Backend",
        service=BACKEND,
    ),
    Setting(
        key="BACKEND_PORT",
        label="Backend-Port (Bindung)",
        group="Backend",
        service=BACKEND,
        kind="int",
    ),
    Setting(
        key="CHROMA_HOST",
        label="Chroma-Host",
        group="Wissensdatenbank",
        service=MCP,
        help="Leer = eingebetteter Store auf der Platte, sonst Chroma-Server.",
    ),
    Setting(
        key="CHROMA_PORT",
        label="Chroma-Port",
        group="Wissensdatenbank",
        service=MCP,
        kind="int",
    ),
    Setting(
        key="CHROMA_COLLECTION",
        label="Collection",
        group="Wissensdatenbank",
        service=MCP,
        help="Name der Chroma-Collection.",
    ),
    Setting(
        key="EMBED_MODEL",
        label="Embedding-Modell",
        group="Wissensdatenbank",
        service=MCP,
        help=(
            "Sentence-Transformers-Modell. Ein Wechsel passt nicht zu bereits "
            "gespeicherten Vektoren - die Datenbank sollte danach neu befüllt werden."
        ),
    ),
    Setting(
        key="DOCS_DIR",
        label="Dokumentenordner",
        group="Wissensdatenbank",
        service=MCP,
        help="Ordner, den `ingest_documents` einliest.",
    ),
    Setting(
        key="UPLOAD_DIR",
        label="Upload-Ordner",
        group="Wissensdatenbank",
        service=MCP,
        help="Hier landen hochgeladene Dateien und Bilder.",
    ),
    Setting(
        key="JOBSUCHE_API_URL",
        label="Jobsuche-API",
        group="Jobbörse",
        service=JOBSUCHE,
        kind="url",
        help="Basis-URL der Arbeitsagentur-Jobsuche.",
    ),
    Setting(
        key="JOBSUCHE_API_KEY",
        label="Jobsuche-API-Key",
        group="Jobbörse",
        service=JOBSUCHE,
        kind="secret",
        help="Öffentlicher Key der Jobbörse; Standard jobboerse-jobsuche.",
    ),
    Setting(
        key="JOBSUCHE_SERVICE_URL",
        label="Jobsuche-Microservice",
        group="Jobbörse",
        service=MCP,
        help="Leer = der MCP-Server ruft die API direkt auf.",
    ),
    Setting(
        key="JOBSUCHE_SERVICE_HOST",
        label="Microservice-Host (Bindung)",
        group="Jobbörse",
        service=JOBSUCHE,
    ),
    Setting(
        key="JOBSUCHE_SERVICE_PORT",
        label="Microservice-Port (Bindung)",
        group="Jobbörse",
        service=JOBSUCHE,
        kind="int",
    ),
    Setting(
        key="BRAVE_API_KEY",
        label="Brave-API-Key",
        group="Unternehmens-Recherche",
        service=MCP,
        kind="secret",
        help="Optional. Ohne Key entfällt nur die Websuche.",
    ),
    Setting(
        key="BRAVE_SEARCH_URL",
        label="Brave-Such-URL",
        group="Unternehmens-Recherche",
        service=MCP,
        kind="url",
    ),
    Setting(
        key="WIKIDATA_SPARQL_URL",
        label="Wikidata-SPARQL",
        group="Unternehmens-Recherche",
        service=MCP,
        kind="url",
    ),
    Setting(
        key="NOMINATIM_URL",
        label="Nominatim (OpenStreetMap)",
        group="Unternehmens-Recherche",
        service=MCP,
        kind="url",
    ),
    Setting(
        key="COMPANY_RESEARCH_LANG",
        label="Sprache der Recherche",
        group="Unternehmens-Recherche",
        service=MCP,
        kind="choice",
        choices=("de", "en"),
        help="Bevorzugte Wikipedia-Sprachversion.",
    ),
    Setting(
        key="COMPANY_RESEARCH_TIMEOUT",
        label="Timeout je Quelle (s)",
        group="Unternehmens-Recherche",
        service=MCP,
        kind="float",
    ),
)

BY_KEY: dict[str, Setting] = {s.key: s for s in CATALOGUE}

_lock = threading.Lock()


def _current(setting: Setting) -> str:
    """The value the processes are running with right now."""
    value = getattr(config, setting.key, None)
    if value is None:
        value = os.getenv(setting.key, "")
    if isinstance(value, (frozenset, set, tuple, list)):
        return ",".join(sorted(str(v) for v in value))
    return str(value)


def _overrides() -> dict[str, str]:
    """The keys currently pinned in the override file."""
    path = Path(config.SETTINGS_FILE)
    if not path.exists():
        return {}

    values: dict[str, str] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue
        key, _, raw = stripped.partition("=")
        values[key.strip()] = _unquote(raw.strip())
    return values


def describe() -> dict[str, Any]:
    """The catalogue plus current values, grouped for the UI."""
    overridden = _overrides()
    groups: dict[str, list[dict[str, Any]]] = {}

    for setting in CATALOGUE:
        value = _current(setting)
        entry: dict[str, Any] = {
            "key": setting.key,
            "label": setting.label,
            "kind": setting.kind,
            "help": setting.help,
            "service": setting.service,
            "service_label": SERVICE_LABELS[setting.service],
            "live": setting.live,
            "overridden": setting.key in overridden,
            "value": "" if setting.kind == "secret" else value,
            "is_set": bool(value),
        }
        if setting.choices:
            entry["choices"] = list(setting.choices)
        groups.setdefault(setting.group, []).append(entry)

    return {
        "file": str(config.SETTINGS_FILE),
        "writable": is_writable(),
        "groups": [{"name": name, "settings": items} for name, items in groups.items()],
    }


def update(values: dict[str, Any], on_live_change: Callable[[], None] | None = None) -> dict[str, Any]:
    """
    Validate, persist and - where possible - apply the submitted values.

    Only keys from the catalogue are accepted: this endpoint must not become a
    way to inject arbitrary environment variables into the processes.
    """
    if not isinstance(values, dict) or not values:
        raise SettingsError("no settings submitted")

    unknown = sorted(set(values) - set(BY_KEY))
    if unknown:
        raise SettingsError(f"unknown setting(s): {', '.join(unknown)}")

    cleaned = {key: _validate(BY_KEY[key], values[key]) for key in values}

    with _lock:
        try:
            _write_env_file(Path(config.SETTINGS_FILE), cleaned)
        except OSError as exc:
            raise SettingsError(_not_writable_message(exc), status=500) from exc

        applied: list[str] = []
        for key, value in cleaned.items():
            os.environ[key] = value
            if BY_KEY[key].live:
                _apply_live(key, value)
                applied.append(key)

        if applied and on_live_change is not None:
            on_live_change()

    restart: dict[str, list[str]] = {}
    for key in cleaned:
        setting = BY_KEY[key]
        if setting.restart_required:
            restart.setdefault(setting.service, []).append(key)

    return {
        "saved": sorted(cleaned),
        "applied": sorted(applied),
        "restart_required": [
            {"service": service, "label": SERVICE_LABELS[service], "settings": sorted(keys)}
            for service, keys in sorted(restart.items())
        ],
        "warnings": _reachability_warnings(cleaned),
        "file": str(config.SETTINGS_FILE),
    }

_PROBES = {
    "OLLAMA_BASE_URL": ("Ollama", "/api/tags"),
    "MCP_URL": ("Der MCP-Server", ""),
    "JOBSUCHE_SERVICE_URL": ("Der Jobsuche-Service", "/health"),
}


def _reachability_warnings(cleaned: dict[str, str]) -> list[str]:
    """
    Check the URLs that were just changed and report the dead ones.
    """
    warnings: list[str] = []
    for key, (label, path) in _PROBES.items():
        url = cleaned.get(key, "").strip()
        if not url:
            continue
        reachable, detail = _probe(url.rstrip("/") + path)
        if not reachable:
            warnings.append(
                f"{label} ist unter {url} nicht erreichbar ({detail})."
                + _localhost_hint(url)
            )
    return warnings


def _probe(url: str) -> tuple[bool, str]:
    """Any HTTP answer means reachable; only the connection itself matters."""
    try:
        with httpx.Client(timeout=3) as client:
            client.get(url)
        return True, ""
    except httpx.HTTPError as exc:
        return False, type(exc).__name__


def _localhost_hint(url: str) -> str:
    """The classic mix-up: an address that is only right outside the container."""
    host = (urlsplit(url).hostname or "").lower()
    if not in_container() or host not in {"localhost", "127.0.0.1", "::1", "0.0.0.0"}:
        return ""
    return (
        " Dieser Dienst läuft in einem Container: 'localhost' zeigt dort auf den"
        " Container selbst. Für einen Dienst auf dem Host-Rechner"
        " 'host.docker.internal' verwenden, für einen anderen Container dessen"
        " Servicenamen (z.B. http://mcp:8000/mcp)."
    )


def in_container() -> bool:
    return Path("/.dockerenv").exists()


def _not_writable_message(exc: OSError) -> str:
    return (
        f"Die Einstellungsdatei '{config.SETTINGS_FILE}' ist nicht beschreibbar "
        f"({exc.strerror or exc}). In Docker gehört das Verzeichnis dem Benutzer "
        "'app' (uid 1000); nach einem Update der Images hilft "
        "'docker compose down && docker volume rm aai_settings && docker compose up --build'."
    )


def is_writable() -> bool:
    """Whether the settings file could be written right now."""
    path = Path(config.SETTINGS_FILE)
    target = path if path.exists() else path.parent
    return os.access(target, os.W_OK)


def _validate(setting: Setting, raw: Any) -> str:
    if raw is None:
        raw = ""
    if isinstance(raw, bool):
        raw = "true" if raw else "false"
    if not isinstance(raw, (str, int, float)):
        raise SettingsError(f"{setting.key}: expected a scalar value")

    value = str(raw).strip()

    if setting.kind == "int":
        if not _is_int(value):
            raise SettingsError(f"{setting.label}: '{value}' ist keine ganze Zahl")
    elif setting.kind == "float":
        try:
            float(value)
        except ValueError:
            raise SettingsError(f"{setting.label}: '{value}' ist keine Zahl") from None
    elif setting.kind == "url":
        if value and not value.startswith(("http://", "https://")):
            raise SettingsError(f"{setting.label}: muss mit http:// oder https:// beginnen")
    elif setting.kind == "choice" and value not in setting.choices:
        raise SettingsError(
            f"{setting.label}: erlaubt sind {', '.join(setting.choices)}"
        )
    elif setting.kind == "csv":
        value = ",".join(part.strip() for part in value.split(",") if part.strip())

    if "\n" in value or "\r" in value:
        raise SettingsError(f"{setting.label}: Zeilenumbrüche sind nicht erlaubt")
    return value


def _is_int(value: str) -> bool:
    return bool(value) and (value[1:] if value[0] in "+-" else value).isdigit()


def _apply_live(key: str, value: str) -> None:
    """Re-bind a value on the modules the backend reads it from."""
    setting = BY_KEY[key]

    if setting.kind == "int":
        setattr(config, key, int(value))
    elif setting.kind == "float":
        setattr(config, key, float(value))
    elif key == "ALLOWED_IMAGE_TYPES":
        types = frozenset(t.strip() for t in value.split(",") if t.strip())
        config.ALLOWED_IMAGE_TYPES = types
    else:
        setattr(config, key, value)

    if key == "OLLAMA_BASE_URL":
        config.OLLAMA_OPENAI_URL = f"{value.rstrip('/')}/v1"

    _mirror_to_attachments(key)


def _mirror_to_attachments(key: str) -> None:
    """`backend.attachments` copies two limits into module constants."""
    if key not in {"MAX_UPLOAD_MB", "ALLOWED_IMAGE_TYPES"}:
        return

    from backend import attachments

    attachments.MAX_UPLOAD_MB = config.MAX_UPLOAD_MB
    attachments.MAX_UPLOAD_BYTES = config.MAX_UPLOAD_MB * 1024 * 1024
    attachments.ALLOWED_IMAGE_TYPES = config.ALLOWED_IMAGE_TYPES

_HEADER = (
    "# Written by the settings page of the Job Application Agent.",
    "# Loaded last by config.py and with override=True, so these values win",
    "# over .env and over the container environment. Delete a line to fall back.",
    "",
)


def _write_env_file(path: Path, updates: dict[str, str]) -> None:
    """Update keys in place, keeping comments and the order of the file."""
    existing = path.read_text(encoding="utf-8").splitlines() if path.exists() else list(_HEADER)
    pending = dict(updates)
    lines: list[str] = []

    for line in existing:
        stripped = line.strip()
        if stripped and not stripped.startswith("#") and "=" in stripped:
            key = stripped.partition("=")[0].strip()
            if key in pending:
                lines.append(f"{key}={_quote(pending.pop(key))}")
                continue
        lines.append(line)

    if pending:
        if lines and lines[-1].strip().startswith("#"):
            lines.append("")
        lines.extend(f"{key}={_quote(value)}" for key, value in sorted(pending.items()))

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines).rstrip("\n") + "\n", encoding="utf-8")


def _quote(value: str) -> str:
    if value == "" or any(ch in value for ch in ' #"\''):
        return '"' + value.replace("\\", "\\\\").replace('"', '\\"') + '"'
    return value


def _unquote(value: str) -> str:
    if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
        return value[1:-1].replace('\\"', '"').replace("\\\\", "\\")
    return value
