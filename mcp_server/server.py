"""
MCP server exposing the shared tool layer for the Job Application system.

Job board (Arbeitsagentur) -> Needs to be adjusted for other APIs!
- search_jobs        – search and (by default) cache offers in the RAG store
- get_job_details    – fetch the full description for one offer

Knowledge base (ChromaDB RAG)
- store_jobs         – persist arbitrary job dicts as searchable text
- query_knowledge    – semantic search across all stored documents
- get_profile_context – pull the user's relevant CV/preference chunks
- list_knowledge     – counts per document type
- ingest_documents   – load the user's personal docs (CV, preferences …)
"""

from __future__ import annotations

from typing import Any, Optional

from mcp.server.fastmcp import FastMCP

from config import MCP_HOST, MCP_PORT, MCP_PATH, DOCS_DIR, JOBSUCHE_SERVICE_URL
from core_functions.arbeitsagentur_jobsuche_API_jobs_client import JobsucheClient
from core_functions.jobsuche_service_client import JobsucheServiceClient
from core_functions.rag_store import JobApplicationStore


mcp = FastMCP(
    "JobBoard",
    host=MCP_HOST,
    port=MCP_PORT,
    streamable_http_path=MCP_PATH,
)

_jobs_client: Optional[JobsucheClient | JobsucheServiceClient] = None
_store: Optional[JobApplicationStore] = None


def _jobs() -> JobsucheClient | JobsucheServiceClient:
    """Route through the jobsuche microservice if one is configured."""
    global _jobs_client
    if _jobs_client is None:
        _jobs_client = (
            JobsucheServiceClient(JOBSUCHE_SERVICE_URL)
            if JOBSUCHE_SERVICE_URL
            else JobsucheClient()
        )
    return _jobs_client


def _rag() -> JobApplicationStore:
    global _store
    if _store is None:
        _store = JobApplicationStore()
    return _store


@mcp.tool()
def search_jobs(
    was: str,
    wo: str = "",
    berufsfeld: str = "",
    umkreis: int = 0,
    arbeitszeit: str = "",
    befristung: str = "",
    size: int = 10,
    store: bool = True,
) -> dict[str, Any]: # TODO: For now only Arbeitsagentur. Later needs to be adjusted to use different APIs.
    """
    Search job offers on the Arbeitsagentur job board.

    Args:
        was: Job title / role / keywords.
        wo: Location.
        berufsfeld: Optional occupational field filter.
        umkreis: Search radius in km around (0 = ignore).
        arbeitszeit: "vz" (full-time) / "tz" (part-time) / "ho" (home office).
        befristung: "1" (befristet) / "2" (unbefristet).
        size: Max number of results (default 10).
        store: If true, the found offers are also saved into the knowledge base.

    Returns:
        {"count": int, "stored": int, "jobs": [ {job summary}, ... ]}.
        An empty "jobs" list means nothing matched, suggest relaxing filters.
    """
    results = _jobs().search(
        was=was,
        wo=wo or None,
        berufsfeld=berufsfeld or None,
        umkreis=umkreis or None,
        arbeitszeit=arbeitszeit or None,
        befristung=befristung or None,
        size=size,
    )
    jobs = [j.to_dict() for j in results]

    stored = 0
    if store and jobs:
        stored = _rag().add_jobs(jobs)

    return {"count": len(jobs), "stored": stored, "jobs": jobs}


@mcp.tool()
def get_job_details(referenznummer: str) -> dict[str, Any]:
    """
    Fetch the full details (description, requirements, benefits, contact) for a
    single job offer identified by its referenznummer.
    """
    details = _jobs().get_details(referenznummer)
    return details.to_dict()


@mcp.tool()
def store_jobs(jobs: list[dict]) -> dict[str, int]:
    """
    Persist a list of job dicts into the knowledge base as searchable text.

    Use this to save offers that did not come straight from `search_jobs`
    (which already stores by default). Returns {"stored": <count>}.
    """
    return {"stored": _rag().add_jobs(jobs)}


@mcp.tool()
def query_knowledge(
    query: str,
    doc_types: Optional[list[str]] = None,
    n_results: int = 5,
) -> list[dict]:
    """
    Semantic search across the knowledge base.

    Args:
        query: Natural-language search text.
        doc_types: Restrict the search to one or more types: "lebenslauf", "noten", "zeugnis". None searches everything.
        n_results: How many chunks to return.
    """
    return _rag().query(query, doc_types=doc_types, n_results=n_results)


@mcp.tool()
def get_profile_context(job_description: str) -> str:
    """
    Return the users most relevant CV, preference and reference snippets for a
    given job description, ready to drop into a prompt as context.
    """
    return _rag().get_profile_context(job_description)


@mcp.tool()
def list_knowledge() -> dict[str, int]:
    """Return how many chunks are stored per document type."""
    return _rag().list_documents()


@mcp.tool()
def ingest_documents(docs_dir: str = "") -> dict[str, int]:
    """
    Ingest the users personal documents (CV, motivation, preferences, grades, employment reference) from a
    folder into the knowledge base. Defaults to the configured DOCS_DIR.
    Returns a mapping {filename: chunks_stored}.
    """
    return _rag().add_all_documents(docs_dir or DOCS_DIR)


def run() -> None:
    mcp.run(transport="streamable-http")


if __name__ == "__main__":
    run()
