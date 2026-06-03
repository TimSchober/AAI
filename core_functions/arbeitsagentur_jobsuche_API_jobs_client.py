"""
HTTP client for the Bundesagentur für Arbeit Jobsuche API.
URL: https://rest.arbeitsagentur.de/jobboerse/jobsuche-serviced

Endpoints used:
GET /pc/v6/jobs          – search jobs
GET /pc/v4/jobdetails/   – fetch job details
"""

from __future__ import annotations

import base64
from dataclasses import dataclass
from typing import Any

import httpx

from config import JOBSUCHE_API_KEY, JOBSUCHE_API_URL


@dataclass
class JobSummary:
    referenznummer: str
    titel: str
    arbeitgeber_name: str
    ort: str
    beschaeftigungsgrad: str
    angebotsart: str
    arbeitszeit: str
    befristung: str
    veroeffentlicht_am: str
    url: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "referenznummer": self.referenznummer,
            "titel": self.titel,
            "arbeitgeber": self.arbeitgeber_name,
            "ort": self.ort,
            "beschaeftigungsgrad": self.beschaeftigungsgrad,
            "angebotsart": self.angebotsart,
            "arbeitszeit": self.arbeitszeit,
            "befristung": self.befristung,
            "veroeffentlicht_am": self.veroeffentlicht_am,
            "url": self.url,
        }


@dataclass
class JobDetails(JobSummary):
    text: str = ""
    anforderung: str = ""
    leistungen: str = ""
    kontakt: str = ""

    def to_dict(self) -> dict[str, Any]:
        data = super().to_dict()
        data.update(
            {
                "text": self.text,
                "anforderung": self.anforderung,
                "leistungen": self.leistungen,
                "kontakt": self.kontakt,
            }
        )
        return data


class JobsucheClient:

    def __init__(
        self,
        api_key: str = JOBSUCHE_API_KEY,
        base_url: str = JOBSUCHE_API_URL,
    ):
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self._client = httpx.Client(
            base_url=self.base_url,
            headers={"X-API-Key": self.api_key, "Accept": "application/json"},
            timeout=30.0,
        )


    @staticmethod
    def _base64_refnr(refnr: str) -> str:
        return base64.b64encode(refnr.encode("utf-8")).decode("utf-8")


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
        params: dict[str, Any] = {"page": page, "size": size, "zeitarbeit": zeitarbeit}

        if was:
            params["was"] = was
        if wo:
            params["wo"] = wo
        if berufsfeld:
            params["berufsfeld"] = berufsfeld
        if umkreis:
            params["umkreis"] = umkreis
        if veroeffentlichtseit:
            params["veroeffentlichtseit"] = veroeffentlichtseit
        if angebotsart:
            params["angebotsart"] = angebotsart
        if befristung:
            params["befristung"] = befristung
        if arbeitszeit:
            params["arbeitszeit"] = arbeitszeit
        if arbeitgeber:
            params["arbeitgeber"] = arbeitgeber

        resp = self._client.get("/pc/v4/jobs", params=params)
        resp.raise_for_status()
        data = resp.json()

        jobs: list[JobSummary] = []
        for item in data.get("stellenangebote", data.get("jobs", [])):
            jobs.append(
                JobSummary(
                    referenznummer=item.get("refnr", item.get("referenznummer", "")),
                    titel=item.get("titel", item.get("beruf", "")),
                    arbeitgeber_name=item.get("arbeitgeber", ""),
                    ort=_extract_ort(item),
                    beschaeftigungsgrad=item.get("beschaeftigungsgrad", ""),
                    angebotsart=str(item.get("angebotsart", "")),
                    arbeitszeit=item.get("arbeitszeit", ""),
                    befristung=item.get("befristung", ""),
                    veroeffentlicht_am=item.get("aktuelleVeroeffentlichungsdatum", ""),
                    url=item.get("externeUrl", ""),
                )
            )
        return jobs

    def get_details(self, refnr: str) -> JobDetails:
        encrypted = self._base64_refnr(refnr)
        resp = self._client.get(f"/pc/v4/jobdetails/{encrypted}")
        resp.raise_for_status()
        data = resp.json()

        return JobDetails(
            referenznummer=data.get("referenznummer", refnr),
            titel=data.get("stellenangebotsTitel", ""),
            arbeitgeber_name=data.get("firma", ""),
            ort=_extract_lokationen(data.get("stellenlokationen")),
            beschaeftigungsgrad=str(data.get("stellenangebotsart", "")),
            angebotsart=str(data.get("stellenangebotsart", "")),
            arbeitszeit=_extract_arbeitszeit(data),
            befristung=str(data.get("vertragsdauer", "")),
            veroeffentlicht_am=data.get("datumErsteVeroeffentlichung", ""),
            url=data.get("externeURL", ""),
            text=data.get("stellenangebotsBeschreibung", ""),
            anforderung=data.get("fertigkeiten", "") or "",
            leistungen=data.get("verguetungsangabe", "") or "",
            kontakt=data.get("arbeitgeberdarstellung", "") or "",
        )

    def close(self) -> None:
        self._client.close()

    def __enter__(self) -> "JobsucheClient":
        return self

    def __exit__(self, *args) -> None:
        self.close()


def _extract_ort(item: dict[str, Any]) -> str:
    arbeitsort = item.get("arbeitsort")
    if isinstance(arbeitsort, dict):
        ort = arbeitsort.get("ort", "")
        plz = arbeitsort.get("plz", "")
        return f"{plz} {ort}".strip() if plz else ort
    return item.get("ort", "")


def _extract_lokationen(lokationen: Any) -> str:
    if isinstance(lokationen, list) and lokationen:
        loc = lokationen[0]
        if isinstance(loc, dict):
            plz = loc.get("plz", "")
            ort = loc.get("ort", "")
            return f"{plz} {ort}".strip() if plz else ort
    return ""


def _extract_arbeitszeit(data: dict[str, Any]) -> str:
    parts = []
    if data.get("arbeitszeitVollzeit"):
        parts.append("Vollzeit")
    if any(
        data.get(k)
        for k in (
            "arbeitszeitTeilzeitAbend",
            "arbeitszeitTeilzeitNachmittag",
            "arbeitszeitTeilzeitVormittag",
            "arbeitszeitTeilzeitFlexibel",
        )
    ):
        parts.append("Teilzeit")
    if data.get("homeofficemoeglich"):
        parts.append("Homeoffice möglich")
    return ", ".join(parts)
