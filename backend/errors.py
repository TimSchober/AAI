"""
Turning failed dependencies into something a user can act on.
"""

from __future__ import annotations

import httpx

import config


def is_connection_error(exc: BaseException) -> bool:
    """True when anything in the cause chain is a failure to connect."""
    seen: set[int] = set()
    current: BaseException | None = exc
    while current is not None and id(current) not in seen:
        seen.add(id(current))
        if isinstance(current, (httpx.ConnectError, httpx.ConnectTimeout, ConnectionError)):
            return True
        current = current.__cause__ or current.__context__
    return False


def friendly_message(exc: BaseException) -> str:
    """The message an agent turn shows when it could not reach a dependency."""
    if not is_connection_error(exc):
        return str(exc)
    return (
        f"Ein benötigter Dienst ist nicht erreichbar ({exc}). "
        f"Sprachmodell: {config.OLLAMA_BASE_URL}, MCP-Server: {config.MCP_URL}. "
        "Welcher Dienst fehlt, zeigt /ready; die Adressen stehen unter "
        "Einstellungen."
    )
