"""
Client for researching the employer behind a job offer.
"""

from __future__ import annotations

import re
from dataclasses import asdict, dataclass, field
from typing import Any, Optional
from urllib.parse import quote

import httpx

from config import (
    BRAVE_API_KEY,
    BRAVE_SEARCH_URL,
    COMPANY_RESEARCH_LANG,
    COMPANY_RESEARCH_TIMEOUT,
    NOMINATIM_URL,
    WIKIDATA_SPARQL_URL,
)

USER_AGENT = "JobApplicationAgent/1.0 (company research; +https://github.com/TimSchober/AAI)"

_LEGAL_FORMS = re.compile(
    r"\b("
    r"gmbh(\s*&\s*co\.?\s*kg)?|mbh|ag|se|kg|ohg|gbr|ug|e\.?\s?k\.?|e\.?\s?v\.?|"
    r"ggmbh|kgaa|ltd\.?|plc|inc\.?|corp\.?|llc|s\.?a\.?|b\.?v\.?|n\.?v\.?|"
    r"co\.?\s?kg|und\s+co\.?\s?kg"
    r")\b\.?",
    re.IGNORECASE,
)
_NOISE = re.compile(r"[|·•]|\s+-\s+.*$")

_BRANCH = re.compile(
    r"\s*\b(zweig)?niederlassung\b.*$|\s*\bnl\b\s+\S.*$|\s*\b(standort|filiale|"
    r"werk|betriebsstätte|geschäftsstelle|region)\b\s+\S.*$",
    re.IGNORECASE,
)

_NOT_A_WORKPLACE = frozenset(
    {"highway", "boundary", "place", "waterway", "natural", "railway", "landuse"}
)


def normalize_company_name(name: str) -> str:
    """Strip legal form and trailing noise so the name can be looked up."""
    cleaned = _NOISE.sub(" ", name or "")
    cleaned = _BRANCH.sub(" ", cleaned)
    cleaned = _LEGAL_FORMS.sub(" ", cleaned)
    cleaned = re.sub(r"[,;]+", " ", cleaned)
    return re.sub(r"\s+", " ", cleaned).strip(" -&+.") or (name or "").strip()


@dataclass
class WebResult:
    title: str
    url: str
    snippet: str = ""
    age: str = ""


@dataclass
class CompanyProfile:
    """Fields stay empty if unknown."""

    name: str
    query: str = ""
    summary: str = ""
    industry: str = ""
    founded: str = ""
    headquarters: str = ""
    employees: str = ""
    revenue: str = ""
    website: str = ""
    ceo: str = ""
    country: str = ""
    address: str = ""
    wikipedia_url: str = ""
    wikidata_id: str = ""
    sources: list[str] = field(default_factory=list)
    web_results: list[WebResult] = field(default_factory=list)

    @property
    def found(self) -> bool:
        return bool(self.summary or self.industry or self.address or self.web_results)

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["found"] = self.found
        return data

    def to_text(self) -> str:
        """Flat text for the knowledge base."""
        rows = [
            ("Unternehmen", self.name),
            ("Branche", self.industry),
            ("Gegründet", self.founded),
            ("Hauptsitz", self.headquarters),
            ("Adresse", self.address),
            ("Mitarbeitende", self.employees),
            ("Umsatz", self.revenue),
            ("Geschäftsführung", self.ceo),
            ("Land", self.country),
            ("Website", self.website),
            ("Wikipedia", self.wikipedia_url),
        ]
        lines = [f"{label}: {value}" for label, value in rows if value]
        if self.summary:
            lines.append(f"Profil: {self.summary}")
        for result in self.web_results:
            lines.append(f"Web: {result.title} - {result.url} - {result.snippet}")
        if self.sources:
            lines.append(f"Quellen: {', '.join(self.sources)}")
        return "\n".join(lines)


class CompanyResearchClient:
    """Looks an employer up across the free sources listed in the module docstring."""

    def __init__(
        self,
        lang: str = COMPANY_RESEARCH_LANG,
        timeout: float = COMPANY_RESEARCH_TIMEOUT,
        brave_api_key: str = BRAVE_API_KEY,
    ) -> None:
        self.lang = lang or "de"
        self.brave_api_key = brave_api_key
        self._client = httpx.Client(
            timeout=timeout,
            follow_redirects=True,
            headers={"User-Agent": USER_AGENT, "Accept": "application/json"},
        )

    @property
    def web_search_available(self) -> bool:
        return bool(self.brave_api_key)

    def research(
        self,
        name: str,
        location: str = "",
        with_web_search: bool = True,
    ) -> CompanyProfile:
        """Build one profile for `name`, using every source that answers."""
        query = normalize_company_name(name)
        profile = CompanyProfile(name=name.strip() or query, query=query)
        if not query:
            return profile

        self._add_wikipedia(profile)
        if profile.wikidata_id:
            self._add_wikidata(profile)
        self._add_location(profile, location)
        if with_web_search and self.web_search_available:
            profile.web_results = self.web_search(
                f"{query} {location} Unternehmen".strip(), count=5
            )
            if profile.web_results:
                profile.sources.append("brave")
        return profile

    def web_search(self, query: str, count: int = 5) -> list[WebResult]:
        """Free-text web search. Returns [] when no Brave key is configured."""
        if not self.web_search_available or not query.strip():
            return []
        data = self._get(
            BRAVE_SEARCH_URL,
            params={"q": query, "count": max(1, min(count, 20)), "country": "de"},
            headers={
                "X-Subscription-Token": self.brave_api_key,
                "Accept": "application/json",
            },
        )
        results = ((data or {}).get("web") or {}).get("results") or []
        return [
            WebResult(
                title=_clean(item.get("title", "")),
                url=item.get("url", ""),
                snippet=_clean(item.get("description", "")),
                age=item.get("age", "") or "",
            )
            for item in results[:count]
        ]

    def close(self) -> None:
        self._client.close()

    def _add_wikipedia(self, profile: CompanyProfile) -> None:
        """Find the article for the company and take its summary."""
        for lang in _languages(self.lang):
            for title in self._wikipedia_titles(profile, lang):
                slug = quote(title.replace(" ", "_"), safe="")
                summary = self._get(
                    f"https://{lang}.wikipedia.org/api/rest_v1/page/summary/{slug}"
                )
                if not summary or summary.get("type") == "disambiguation":
                    continue

                qid = summary.get("wikibase_item", "") or ""
                # Many firms are named after their founder ("Robert Bosch GmbH"),
                # and the person outranks the company in the search. Skip humans.
                if qid and self._is_person(qid):
                    continue

                profile.summary = _clean(summary.get("extract", ""))
                profile.wikidata_id = qid
                profile.wikipedia_url = (
                    ((summary.get("content_urls") or {}).get("desktop") or {}).get(
                        "page", ""
                    )
                )
                profile.sources.append(f"wikipedia:{lang}")
                return

    def _wikipedia_titles(self, profile: CompanyProfile, lang: str) -> list[str]:
        """Candidate articles for the employer, most promising first."""
        data = self._get(
            f"https://{lang}.wikipedia.org/w/api.php",
            params={
                "action": "query",
                "list": "search",
                "srsearch": (
                    f"{profile.query} Unternehmen"
                    if lang == "de"
                    else f"{profile.query} company"
                ),
                "srlimit": 5,
                "format": "json",
            },
        )
        hits = [
            hit.get("title", "")
            for hit in ((data or {}).get("query") or {}).get("search") or []
            if hit.get("title")
        ]
        if not hits:
            return []

        full = _key(profile.name)
        wanted = _key(profile.query)
        candidates = [
            *[t for t in hits if _key(t) == full],
            *[t for t in hits if _key(t).startswith(wanted)],
        ]

        ordered: list[str] = []
        for title in candidates:
            if title not in ordered:
                ordered.append(title)
        return ordered[:3]

    def _is_person(self, qid: str) -> bool:
        data = self._get(
            WIKIDATA_SPARQL_URL,
            params={"query": f"ASK {{ wd:{qid} wdt:P31 wd:Q5 }}", "format": "json"},
            headers={"Accept": "application/sparql-results+json"},
        )
        return bool((data or {}).get("boolean"))

    def _add_wikidata(self, profile: CompanyProfile) -> None:
        """Pull the structured facts for the article's Wikidata item."""
        sparql = """
SELECT ?industryLabel ?inception ?hqLabel ?employees ?revenue ?website
       ?ceoLabel ?countryLabel WHERE {
  VALUES ?company { wd:%s }
  OPTIONAL { ?company wdt:P452 ?industry }
  OPTIONAL { ?company wdt:P571 ?inception }
  OPTIONAL { ?company wdt:P159 ?hq }
  OPTIONAL { ?company wdt:P1128 ?employees }
  OPTIONAL { ?company wdt:P2139 ?revenue }
  OPTIONAL { ?company wdt:P856 ?website }
  OPTIONAL { ?company wdt:P169 ?ceo }
  OPTIONAL { ?company wdt:P17 ?country }
  SERVICE wikibase:label { bd:serviceParam wikibase:language "%s,en". }
}
LIMIT 20
""" % (profile.wikidata_id, self.lang)

        data = self._get(
            WIKIDATA_SPARQL_URL,
            params={"query": sparql, "format": "json"},
            headers={"Accept": "application/sparql-results+json"},
        )
        rows = ((data or {}).get("results") or {}).get("bindings") or []
        if not rows:
            return

        def pick(key: str) -> str:
            """First non-empty value across rows; OPTIONALs fan out into several."""
            for row in rows:
                value = (row.get(key) or {}).get("value", "").strip()
                if value:
                    return value
            return ""

        profile.industry = profile.industry or pick("industryLabel")
        profile.headquarters = profile.headquarters or pick("hqLabel")
        profile.ceo = profile.ceo or pick("ceoLabel")
        profile.country = profile.country or pick("countryLabel")
        profile.website = profile.website or pick("website")
        profile.founded = profile.founded or pick("inception")[:4]
        profile.employees = profile.employees or _number(pick("employees"))
        revenue = _number(pick("revenue"))
        profile.revenue = profile.revenue or (f"{revenue} EUR" if revenue else "")
        profile.sources.append("wikidata")

    def _add_location(self, profile: CompanyProfile, location: str) -> None:
        """Look the employer up on the map - this is what small firms are in."""
        results = self._get(
            NOMINATIM_URL,
            params={
                "q": f"{profile.query} {location}".strip(),
                "format": "jsonv2",
                "limit": 1,
                "addressdetails": 1,
                "extratags": 1,
                "accept-language": self.lang,
            },
        )
        if not isinstance(results, list) or not results:
            return

        hit = results[0]
        if not _key(hit.get("name", "")).startswith(_key(profile.query)):
            return
        if hit.get("category") in _NOT_A_WORKPLACE:
            return

        profile.address = _clean(hit.get("display_name", ""))
        extratags = hit.get("extratags") or {}
        profile.website = profile.website or extratags.get("website", "") or ""
        profile.industry = profile.industry or _clean(extratags.get("industry", ""))
        profile.sources.append("openstreetmap")

    def _get(
        self,
        url: str,
        params: Optional[dict[str, Any]] = None,
        headers: Optional[dict[str, str]] = None,
    ) -> Any:
        """GET returning parsed JSON, or None when the source is unavailable."""
        try:
            response = self._client.get(url, params=params, headers=headers)
            response.raise_for_status()
            return response.json()
        except (httpx.HTTPError, ValueError):
            return None


def _languages(primary: str) -> list[str]:
    return [primary] + [lang for lang in ("de", "en") if lang != primary]


def _clean(text: str) -> str:
    return re.sub(r"\s+", " ", text or "").strip()


def _key(text: str) -> str:
    """Comparable form of a name: no qualifier, no punctuation, no case."""
    without_qualifier = re.sub(r"\s*\(.*?\)\s*$", " ", text or "")
    letters = re.sub(r"[^\w\s]", " ", without_qualifier)
    return re.sub(r"\s+", " ", letters).strip().casefold()


def _number(raw: str) -> str:
    """Wikidata numbers arrive as '+370000'; render them with thin separators."""
    digits = raw.lstrip("+").split(".")[0]
    if not digits.isdigit():
        return _clean(raw)
    return f"{int(digits):,}".replace(",", ".")
