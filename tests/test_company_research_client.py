"""
Tests for `core_functions.company_research_client`.
"""

from __future__ import annotations

import httpx
import pytest

from core_functions.company_research_client import (
    CompanyProfile,
    CompanyResearchClient,
    WebResult,
    normalize_company_name,
)


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("Robert Bosch GmbH", "Robert Bosch"),
        ("Muster GmbH & Co. KG", "Muster"),
        ("Beispiel AG - Niederlassung Köln", "Beispiel"),
        ("Beispiel SE, Standort Hamburg", "Beispiel"),
        ("Contoso Ltd.", "Contoso"),
        ("Test Software | Karriere - Jetzt bewerben", "Test Software Karriere"),
        ("  Deutsche Bahn  ", "Deutsche Bahn"),
    ],
)
def test_normalize_strips_legal_form_and_noise(raw: str, expected: str) -> None:
    assert normalize_company_name(raw) == expected


@pytest.mark.parametrize("raw", ["GmbH", "", "   "])
def test_normalize_falls_back_to_the_original_when_nothing_is_left(raw: str) -> None:
    """Stripping must never hand an empty query to the sources."""
    assert normalize_company_name(raw) == raw.strip()


def test_profile_reports_found_only_with_real_content() -> None:
    assert not CompanyProfile(name="Muster GmbH").found
    assert CompanyProfile(name="Muster GmbH", summary="Ein Unternehmen.").found


def test_profile_text_skips_empty_fields() -> None:
    """Only known facts reach the knowledge base - no 'Umsatz: ' noise."""
    profile = CompanyProfile(
        name="Beispiel AG",
        industry="Maschinenbau",
        headquarters="Stuttgart",
        summary="Baut Maschinen.",
        sources=["wikipedia:de"],
    )

    text = profile.to_text()

    assert "Unternehmen: Beispiel AG" in text
    assert "Branche: Maschinenbau" in text
    assert "Profil: Baut Maschinen." in text
    assert "Quellen: wikipedia:de" in text
    assert "Umsatz" not in text
    assert "Website" not in text


def test_profile_dict_carries_the_found_flag() -> None:
    data = CompanyProfile(name="X", web_results=[WebResult(title="t", url="u")]).to_dict()

    assert data["found"] is True
    assert data["web_results"] == [
        {"title": "t", "url": "u", "snippet": "", "age": ""}
    ]


def test_web_search_is_skipped_without_a_brave_key() -> None:
    client = CompanyResearchClient(brave_api_key="")

    assert client.web_search_available is False
    assert client.web_search("Beispiel AG") == []
    client.close()


def test_web_search_parses_brave_results() -> None:
    seen: dict[str, object] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["token"] = request.headers.get("X-Subscription-Token")
        seen["params"] = dict(request.url.params)
        return httpx.Response(
            200,
            json={
                "web": {
                    "results": [
                        {
                            "title": "Beispiel  AG",
                            "url": "https://beispiel.de",
                            "description": "Ein\n Unternehmen",
                            "age": "2 days ago",
                        }
                    ]
                }
            },
        )

    client = CompanyResearchClient(brave_api_key="test-key")
    client._client = httpx.Client(transport=httpx.MockTransport(handler))

    results = client.web_search("Beispiel AG", count=3)
    client.close()

    assert seen["token"] == "test-key"
    assert seen["params"]["q"] == "Beispiel AG"
    assert seen["params"]["count"] == "3"
    assert results == [
        WebResult(
            title="Beispiel AG",
            url="https://beispiel.de",
            snippet="Ein Unternehmen",
            age="2 days ago",
        )
    ]


def test_a_failing_source_yields_no_results_instead_of_raising() -> None:
    """One dead source must not take a research turn down."""

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(503)

    client = CompanyResearchClient(brave_api_key="test-key")
    client._client = httpx.Client(transport=httpx.MockTransport(handler))

    assert client.web_search("Beispiel AG") == []
    client.close()
