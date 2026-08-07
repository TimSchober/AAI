"""
Central configuration for the Job Application Agent.
"""

from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

PACKAGE_ROOT = Path(__file__).resolve().parent
REPO_ROOT = PACKAGE_ROOT.parent

load_dotenv(PACKAGE_ROOT / ".env")
load_dotenv(REPO_ROOT / ".env")

SETTINGS_FILE: str = os.getenv("SETTINGS_FILE", str(PACKAGE_ROOT / ".env.runtime"))
load_dotenv(SETTINGS_FILE, override=True)

# Ollama LLM:
OLLAMA_BASE_URL: str = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
OLLAMA_MODEL: str = os.getenv("OLLAMA_MODEL", "qwen3.5:4b")
OLLAMA_OPENAI_URL: str = f"{OLLAMA_BASE_URL.rstrip('/')}/v1"
OLLAMA_API_KEY: str = os.getenv("OLLAMA_API_KEY", "ollama")

# Arbeitsagentur Jobsuche API:
JOBSUCHE_API_KEY: str = os.getenv("JOBSUCHE_API_KEY", "jobboerse-jobsuche")
JOBSUCHE_API_URL: str = os.getenv(
    "JOBSUCHE_API_URL",
    "https://rest.arbeitsagentur.de/jobboerse/jobsuche-service",
)

JOBSUCHE_SERVICE_URL: str = os.getenv("JOBSUCHE_SERVICE_URL", "")
JOBSUCHE_SERVICE_HOST: str = os.getenv("JOBSUCHE_SERVICE_HOST", "0.0.0.0")
JOBSUCHE_SERVICE_PORT: int = int(os.getenv("JOBSUCHE_SERVICE_PORT", "8100"))

# Company research.
# Wikipedia, Wikidata and OpenStreetMap need no key; Brave is optional and only adds a web/news search.
BRAVE_API_KEY: str = os.getenv("BRAVE_API_KEY", "")
BRAVE_SEARCH_URL: str = os.getenv(
    "BRAVE_SEARCH_URL", "https://api.search.brave.com/res/v1/web/search"
)
WIKIDATA_SPARQL_URL: str = os.getenv(
    "WIKIDATA_SPARQL_URL", "https://query.wikidata.org/sparql"
)
NOMINATIM_URL: str = os.getenv(
    "NOMINATIM_URL", "https://nominatim.openstreetmap.org/search"
)
COMPANY_RESEARCH_LANG: str = os.getenv("COMPANY_RESEARCH_LANG", "de")
COMPANY_RESEARCH_TIMEOUT: float = float(os.getenv("COMPANY_RESEARCH_TIMEOUT", "30"))

CHROMA_DB_PATH: str = os.getenv(
    "CHROMA_DB_PATH",
    str(PACKAGE_ROOT / "ChromaDB" / "chroma_db"),
)
CHROMA_HOST: str = os.getenv("CHROMA_HOST", "")
CHROMA_PORT: int = int(os.getenv("CHROMA_PORT", "8200"))
CHROMA_COLLECTION: str = os.getenv("CHROMA_COLLECTION", "bewerbungsunterlagen")
EMBED_MODEL: str = os.getenv("EMBED_MODEL", "all-MiniLM-L6-v2")
DOCS_DIR: str = os.getenv("DOCS_DIR", str(PACKAGE_ROOT / "ChromaDB" / "docs"))
UPLOAD_DIR: str = os.getenv("UPLOAD_DIR", str(PACKAGE_ROOT / "ChromaDB" / "uploads"))

# MCP server
MCP_HOST: str = os.getenv("MCP_HOST", "127.0.0.1")
MCP_PORT: int = int(os.getenv("MCP_PORT", "8000"))
MCP_PATH: str = os.getenv("MCP_PATH", "/mcp")
MCP_URL: str = os.getenv("MCP_URL", f"http://{MCP_HOST}:{MCP_PORT}{MCP_PATH}")

# Flask backend API
BACKEND_HOST: str = os.getenv("BACKEND_HOST", "0.0.0.0")
BACKEND_PORT: int = int(os.getenv("BACKEND_PORT", "5000"))
BACKEND_CORS_ORIGINS: str = os.getenv("BACKEND_CORS_ORIGINS", "*")
AGENT_TIMEOUT: int = int(os.getenv("AGENT_TIMEOUT", "300"))

# Chat image attachments
MAX_UPLOAD_MB: int = int(os.getenv("MAX_UPLOAD_MB", "10"))
ALLOWED_IMAGE_TYPES: frozenset[str] = frozenset(
    t.strip()
    for t in os.getenv(
        "ALLOWED_IMAGE_TYPES", "image/png,image/jpeg,image/webp,image/gif"
    ).split(",")
    if t.strip()
)
