"""
MCP server exposing the shared tool layer for the Job Application system.

Job board (Arbeitsagentur) -> Needs to be adjusted for other APIs!
- search_jobs        – search and (by default) cache offers in the RAG store
- get_job_details    – fetch the full description for one offer

Employer research (Wikipedia, Wikidata, OpenStreetMap, optionally Brave)
- list_employers      – the employers of the offers found so far
- research_company    – build a profile for one employer and cache it
- company_web_search  – free web search, only with a Brave key configured

Knowledge base (ChromaDB RAG)
- store_jobs         – persist arbitrary job dicts as searchable text
- query_knowledge    – semantic search across all stored documents
- get_profile_context – pull the user's relevant CV/preference chunks
- list_knowledge     – counts per document type
- ingest_documents   – load the user's personal docs (CV, preferences …)
- ingest_image       – store an image sent through the chat
- store_document_text – store text an agent extracted (e.g. read off an image)
"""

from __future__ import annotations

import base64
import binascii
from typing import Any, Optional

from mcp.server.fastmcp import FastMCP

from config import MCP_HOST, MCP_PORT, MCP_PATH, DOCS_DIR, JOBSUCHE_SERVICE_URL
from core_functions.arbeitsagentur_jobsuche_API_jobs_client import JobsucheClient
from core_functions.company_research_client import CompanyResearchClient
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
_company_client: Optional[CompanyResearchClient] = None


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


def _companies() -> CompanyResearchClient:
    global _company_client
    if _company_client is None:
        _company_client = CompanyResearchClient()
    return _company_client


@mcp.tool()
def search_jobs(
    was: str,
    wo: str = "",
    berufsfeld: str = "",
    umkreis: int = 0,
    arbeitszeit: str = "",
    befristung: str = "",
    size: int = 5,
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
def list_employers(limit: int = 20) -> dict[str, Any]:
    """
    List the employers behind the job offers found so far, newest first.

    Use this to offer the user companies to research when they did not name one.

    Returns:
        {"count": int, "employers": [{"arbeitgeber", "ort", "stellen",
        "titel": [...], "recherchiert": bool}, ...]}. `recherchiert` is true
        when a profile for that employer is already in the knowledge base -
        read it with `query_knowledge` instead of researching it again.
    """
    employers = _rag().list_employers(limit=limit)
    return {"count": len(employers), "employers": employers}


@mcp.tool()
def research_company(
    name: str,
    location: str = "",
    store: bool = True,
) -> dict[str, Any]:
    """
    Research the company behind a job offer.

    Combines free sources that need no account: the Wikipedia article, the
    structured facts on Wikidata (industry, founding year, headquarters, staff,
    revenue, management, website) and the OpenStreetMap entry, which is often
    the only hit for a small local employer. Recent web results are added when
    a Brave API key is configured.

    Args:
        name: Employer name exactly as it appears in the job offer; the legal
              form ("GmbH & Co. KG") is stripped automatically.
        location: Town from the offer. Disambiguates namesakes and is what makes
              the map lookup find the right site.
        store: Also save the profile in the knowledge base (default true).

    Returns:
        The profile with a "found" flag. found=false means the sources know
        nothing about this employer - say so plainly instead of guessing, and
        suggest looking at the company website or the contact in the offer.
    """
    profile = _companies().research(name, location=location)
    data = profile.to_dict()

    if store and profile.found:
        data["stored"] = _rag().add_company(
            profile.name, profile.to_text(), ort=location, website=profile.website
        )
    return data


@mcp.tool()
def company_web_search(query: str, count: int = 5) -> dict[str, Any]:
    """
    Search the web for anything the company profile does not cover, e.g. recent
    news, the careers page or reviews.

    Needs a Brave Search key (free tier). Without one this returns
    {"available": false, "results": []} - then rely on `research_company` and
    tell the user that no web search is configured.
    """
    client = _companies()
    results = client.web_search(query, count=count)
    return {
        "available": client.web_search_available,
        "count": len(results),
        "results": [vars(r) for r in results],
    }


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
        doc_types: Restrict the search to one or more types: "lebenslauf",
                   "noten", "zeugnis", "stellenangebot", "unternehmen"
                   (researched employer profiles). None searches everything.
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


@mcp.tool()
def ingest_image(
    filename: str,
    data_base64: str,
    mime_type: str = "image/png",
    caption: str = "",
) -> dict[str, Any]:
    """
    Store an image the user sent in the chat.

    The file is written to the upload folder and a searchable record (filename,
    format, the user's comment) is added to the knowledge base. Returns
    {"source": ..., "path": ..., "stored": <chunks>}; use `source` when adding
    the image's content later with `store_document_text`.
    """
    try:
        data = base64.b64decode(data_base64, validate=True)
    except (binascii.Error, ValueError) as exc:
        raise ValueError(f"data_base64 is not valid base64: {exc}") from exc
    if not data:
        raise ValueError("data_base64 is empty")

    return _rag().add_image(
        filename=filename, data=data, mime_type=mime_type, caption=caption
    )


@mcp.tool()
def store_document_text(text: str, doc_type: str, source: str) -> dict[str, int]:
    """
    Store plain text in the knowledge base.

    Use this for content that has no file of its own - above all what you read
    out of an image the user sent (a CV screenshot, a certificate, a job ad).
    Pass the `source` returned by `ingest_image` so text and image stay linked.

    Args:
        text: The content to store, already transcribed and cleaned up.
        doc_type: One of "lebenslauf", "motivation", "noten", "zeugnis",
                  "praeferenz", "stellenangebot", "unternehmen", "anhang".
        source: Name the content is filed under.
    """
    return {"stored": _rag().add_text(text, doc_type=doc_type, source=source)}


def run() -> None:
    mcp.run(transport="streamable-http")


if __name__ == "__main__":
    run()
