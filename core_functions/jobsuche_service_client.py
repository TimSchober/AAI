"""
Client for the jobsuche microservice (services/jobsuche_api).

Mirrors the interface of JobsucheClient so the MCP server can talk either
directly to the Arbeitsagentur API or through the containerised service
without any call-site changes.
"""

from __future__ import annotations

from typing import Any

import httpx

from config import JOBSUCHE_SERVICE_URL
from core_functions.arbeitsagentur_jobsuche_API_jobs_client import (
    JobDetails,
    JobSummary,
)


def _summary_from_dict(data: dict[str, Any]) -> JobSummary:
    return JobSummary(
        referenznummer=data.get("referenznummer", ""),
        titel=data.get("titel", ""),
        arbeitgeber_name=data.get("arbeitgeber", ""),
        ort=data.get("ort", ""),
        beschaeftigungsgrad=data.get("beschaeftigungsgrad", ""),
        angebotsart=data.get("angebotsart", ""),
        arbeitszeit=data.get("arbeitszeit", ""),
        befristung=data.get("befristung", ""),
        veroeffentlicht_am=data.get("veroeffentlicht_am", ""),
        url=data.get("url", ""),
    )


def _details_from_dict(data: dict[str, Any]) -> JobDetails:
    summary = _summary_from_dict(data)
    return JobDetails(
        referenznummer=summary.referenznummer,
        titel=summary.titel,
        arbeitgeber_name=summary.arbeitgeber_name,
        ort=summary.ort,
        beschaeftigungsgrad=summary.beschaeftigungsgrad,
        angebotsart=summary.angebotsart,
        arbeitszeit=summary.arbeitszeit,
        befristung=summary.befristung,
        veroeffentlicht_am=summary.veroeffentlicht_am,
        url=summary.url,
        text=data.get("text", ""),
        anforderung=data.get("anforderung", ""),
        leistungen=data.get("leistungen", ""),
        kontakt=data.get("kontakt", ""),
    )


class JobsucheServiceClient:
    """Talks to the jobsuche microservice over HTTP."""

    def __init__(self, base_url: str = JOBSUCHE_SERVICE_URL, timeout: float = 60.0):
        self.base_url = base_url.rstrip("/")
        self._client = httpx.Client(
            base_url=self.base_url,
            headers={"Accept": "application/json"},
            timeout=timeout,
        )

    def search(
        self,
        was: str | None = None,
        wo: str | None = None,
        berufsfeld: str | None = None,
        page: int = 1,
        size: int = 10,
        umkreis: int | None = None,
        veroeffentlichtseit: int | None = None,
        angebotsart: int | None = None,
        befristung: str | None = None,
        arbeitszeit: str | None = None,
        arbeitgeber: str | None = None,
        zeitarbeit: bool = True,
    ) -> list[JobSummary]:
        params: dict[str, Any] = {
            "page": page,
            "size": size,
            "zeitarbeit": str(zeitarbeit).lower(),
        }
        optional = {
            "was": was,
            "wo": wo,
            "berufsfeld": berufsfeld,
            "umkreis": umkreis,
            "veroeffentlichtseit": veroeffentlichtseit,
            "angebotsart": angebotsart,
            "befristung": befristung,
            "arbeitszeit": arbeitszeit,
            "arbeitgeber": arbeitgeber,
        }
        params.update({k: v for k, v in optional.items() if v})

        resp = self._client.get("/jobs", params=params)
        resp.raise_for_status()
        return [_summary_from_dict(j) for j in resp.json().get("jobs", [])]

    def get_details(self, refnr: str) -> JobDetails:
        resp = self._client.get(f"/jobs/{refnr}")
        resp.raise_for_status()
        return _details_from_dict(resp.json())

    def close(self) -> None:
        self._client.close()

    def __enter__(self) -> "JobsucheServiceClient":
        return self

    def __exit__(self, *args) -> None:
        self.close()
