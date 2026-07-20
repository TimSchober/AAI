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

# Chroma DB:
CHROMA_DB_PATH: str = os.getenv(
    "CHROMA_DB_PATH",
    str(PACKAGE_ROOT / "ChromaDB" / "chroma_db"),
)
CHROMA_COLLECTION: str = os.getenv("CHROMA_COLLECTION", "bewerbungsunterlagen")
EMBED_MODEL: str = os.getenv("EMBED_MODEL", "all-MiniLM-L6-v2")
DOCS_DIR: str = os.getenv("DOCS_DIR", str(PACKAGE_ROOT / "ChromaDB" / "docs"))

# MCP server
MCP_HOST: str = os.getenv("MCP_HOST", "127.0.0.1")
MCP_PORT: int = int(os.getenv("MCP_PORT", "8000"))
MCP_PATH: str = os.getenv("MCP_PATH", "/mcp")
MCP_URL: str = os.getenv("MCP_URL", f"http://{MCP_HOST}:{MCP_PORT}{MCP_PATH}")
