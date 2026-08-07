"""
Tests for `core_functions.arbeitsagentur_jobsuche_API_jobs_client`.
"""

from __future__ import annotations

import base64

import httpx
import pytest

from core_functions.arbeitsagentur_jobsuche_API_jobs_client import JobsucheClient

SEARCH_RESPONSE = {
    "stellenangebote": [
        {
            "refnr": "10000-1234567890-S",
            "beruf": "Fachinformatiker",
            "titel": "Fachinformatiker (m/w/d) Anwendungsentwicklung",
            "arbeitgeber": "Beispiel GmbH",
            "arbeitsort": {"ort": "Köln", "plz": "50667"},
            "angebotsart": 1,
            "aktuelleVeroeffentlichungsdatum": "2026-01-15",
            "externeUrl": "https://example.invalid/job/1",
        },
        {
            "referenznummer": "10000-9876543210-S",
            "stellenangebotsTitel": "Data Engineer",
            "firma": "Muster AG",
            "stellenlokationen": [{"adresse": {"ort": "Hamburg", "plz": "20095"}}],
            "arbeitszeitVollzeit": True,
            "homeofficemoeglich": True,
            "vertragsdauer": "unbefristet",
            "datumErsteVeroeffentlichung": "2026-02-01",
        },
    ]
}


def _client(handler) -> JobsucheClient:
    """A JobsucheClient whose HTTP calls are answered by `handler`."""
    client = JobsucheClient(api_key="test-key", base_url="https://api.invalid/service/")
    client._client = httpx.Client(
        base_url=client.base_url,
        headers={"X-API-Key": client.api_key, "Accept": "application/json"},
        transport=httpx.MockTransport(handler),
    )
    return client


def test_search_sends_only_the_filters_that_were_set() -> None:
    seen: dict[str, object] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["path"] = request.url.path
        seen["params"] = dict(request.url.params)
        seen["api_key"] = request.headers.get("X-API-Key")
        return httpx.Response(200, json={"stellenangebote": []})

    with _client(handler) as client:
        client.search(was="Data Engineer", wo="Köln", umkreis=25, size=5)

    assert seen["path"] == "/service/pc/v6/jobs"
    assert seen["api_key"] == "test-key"
    assert seen["params"] == {
        "page": "1",
        "size": "5",
        "zeitarbeit": "true",
        "was": "Data Engineer",
        "wo": "Köln",
        "umkreis": "25",
    }
    assert "arbeitgeber" not in seen["params"]
    assert "befristung" not in seen["params"]


def test_search_maps_both_response_shapes_onto_job_summaries() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=SEARCH_RESPONSE)

    with _client(handler) as client:
        jobs = client.search(was="IT")

    assert len(jobs) == 2

    first = jobs[0].to_dict()
    assert first["referenznummer"] == "10000-1234567890-S"
    assert first["titel"] == "Fachinformatiker (m/w/d) Anwendungsentwicklung"
    assert first["arbeitgeber"] == "Beispiel GmbH"
    assert first["ort"] == "50667 Köln"
    assert first["veroeffentlicht_am"] == "2026-01-15"
    assert first["url"] == "https://example.invalid/job/1"

    second = jobs[1].to_dict()
    assert second["referenznummer"] == "10000-9876543210-S"
    assert second["arbeitgeber"] == "Muster AG"
    assert second["ort"] == "20095 Hamburg"
    assert second["arbeitszeit"] == "Vollzeit, Homeoffice möglich"
    assert second["befristung"] == "unbefristet"


def test_search_returns_an_empty_list_when_nothing_matches() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"maxErgebnisse": 0})

    with _client(handler) as client:
        assert client.search(was="Nichts") == []


def test_get_details_addresses_the_offer_by_base64_reference() -> None:
    """The details endpoint takes the reference number base64-encoded in the path."""
    refnr = "10000-1234567890-S"
    seen: dict[str, str] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["path"] = request.url.path
        return httpx.Response(
            200,
            json={
                "referenznummer": refnr,
                "stellenangebotsTitel": "Data Engineer",
                "firma": "Muster AG",
                "stellenlokationen": [{"ort": "Hamburg", "plz": "20095"}],
                "arbeitszeitVollzeit": True,
                "arbeitszeitTeilzeitFlexibel": True,
                "stellenangebotsBeschreibung": "Wir suchen Verstärkung.",
                "fertigkeiten": "Python, SQL",
                "verguetungsangabe": None,
            },
        )

    with _client(handler) as client:
        details = client.get_details(refnr)

    encoded = base64.b64encode(refnr.encode()).decode()
    assert seen["path"] == f"/service/pc/v4/jobdetails/{encoded}"

    data = details.to_dict()
    assert data["titel"] == "Data Engineer"
    assert data["ort"] == "20095 Hamburg"
    assert data["arbeitszeit"] == "Vollzeit, Teilzeit"
    assert data["text"] == "Wir suchen Verstärkung."
    assert data["anforderung"] == "Python, SQL"
    assert data["leistungen"] == ""


def test_an_http_error_from_the_job_board_is_raised() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(500, json={"error": "boom"})

    with _client(handler) as client:
        with pytest.raises(httpx.HTTPStatusError):
            client.search(was="IT")
