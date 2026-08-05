"""
Shared building blocks: the job board client and the RAG store.

Imports are resolved lazily so that pulling in one submodule does not drag in
the other's dependencies. The jobsuche service container, for example, ships
the job board client without chromadb or sentence-transformers.
"""

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:  # for type checkers and IDEs only
    from core_functions.arbeitsagentur_jobsuche_API_jobs_client import (
        JobDetails,
        JobsucheClient,
        JobSummary,
    )
    from core_functions.jobsuche_service_client import JobsucheServiceClient
    from core_functions.rag_store import JobApplicationStore

_EXPORTS = {
    "JobsucheClient": "core_functions.arbeitsagentur_jobsuche_API_jobs_client",
    "JobSummary": "core_functions.arbeitsagentur_jobsuche_API_jobs_client",
    "JobDetails": "core_functions.arbeitsagentur_jobsuche_API_jobs_client",
    "JobsucheServiceClient": "core_functions.jobsuche_service_client",
    "JobApplicationStore": "core_functions.rag_store",
}

__all__ = list(_EXPORTS)


def __getattr__(name: str) -> Any:
    if name not in _EXPORTS:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    from importlib import import_module

    return getattr(import_module(_EXPORTS[name]), name)


def __dir__() -> list[str]:
    return sorted(__all__)
