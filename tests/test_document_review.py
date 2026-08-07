"""
Tests for the document review agent and the retrieval it depends on.
"""

from __future__ import annotations

from typing import Iterator

import pytest
from flask import Flask
from flask.testing import FlaskClient

from agents.document_review_agent import SYSTEM_PROMPT, build_document_review_agent
from backend.app import create_app
from backend.services import AGENT_SPECS
from core_functions.rag_store import _assemble_chunks, _chunk_text


@pytest.fixture
def app() -> Iterator[Flask]:
    application = create_app()
    application.config["TESTING"] = True
    yield application
    application.extensions["async_runtime"].shutdown()


@pytest.fixture
def client(app: Flask) -> FlaskClient:
    return app.test_client()


def test_the_reviewer_is_registered_as_its_own_agent() -> None:
    spec = AGENT_SPECS["document_review"]

    assert spec.builder is build_document_review_agent
    assert spec.name == "Unterlagen-Coach"
    assert spec.description


def test_the_reviewer_is_offered_by_the_api(client: FlaskClient) -> None:
    agents = client.get("/api/agents").get_json()["agents"]

    reviewer = next(a for a in agents if a["id"] == "document_review")
    assert "Lebenslauf" in reviewer["description"]


def test_an_unknown_thread_for_the_reviewer_is_still_a_known_agent(
    client: FlaskClient,
) -> None:
    """A typo in the agent id must 404 - the reviewer's id must not."""
    assert client.post("/api/agents/document_reviewer/chat", json={"message": "x"}).status_code == 404


def test_the_prompt_tells_the_agent_to_read_before_judging() -> None:
    """
    The document is not in the prompt, so the whole review depends on the agent
    calling get_document first and not inventing content when it finds nothing.
    """
    assert "get_document" in SYSTEM_PROMPT
    assert "list_knowledge" in SYSTEM_PROMPT
    assert "found=false" in SYSTEM_PROMPT
    assert "Erfinde keine" in SYSTEM_PROMPT


def test_chunks_are_reassembled_in_writing_order() -> None:
    documents = ["dritter", "erster", "zweiter"]
    metadatas = [{"chunk_index": 2}, {"chunk_index": 0}, {"chunk_index": 1}]

    assert _assemble_chunks(documents, metadatas) == "erster\nzweiter\ndritter"


def test_chunks_without_an_index_keep_the_order_they_arrived_in() -> None:
    assert _assemble_chunks(["a", "b"], [{}, {}]) == "a\nb"


def test_assembling_nothing_yields_nothing() -> None:
    assert _assemble_chunks([], []) == ""


def test_the_overlap_between_chunks_is_stitched_not_repeated() -> None:
    """
    Chunks are stored with CHUNK_OVERLAP characters of overlap. Joining them
    naively hands the model the same sentence twice at every seam.
    """
    text = "".join(f"Satz Nummer {n} mit etwas Inhalt. " for n in range(60))
    chunks = _chunk_text(text)
    assert len(chunks) > 1  # otherwise this proves nothing

    rebuilt = _assemble_chunks(
        chunks, [{"chunk_index": i} for i in range(len(chunks))]
    )

    assert rebuilt == text.strip()


def test_a_short_coincidental_ending_is_not_treated_as_a_seam() -> None:
    """'... und ' at both ends is a coincidence, not an overlap to swallow."""
    rebuilt = _assemble_chunks(
        ["Erster Teil und ", "und zweiter Teil"], [{"chunk_index": 0}, {"chunk_index": 1}]
    )

    assert "zweiter Teil" in rebuilt
    assert rebuilt.count("Erster Teil") == 1
