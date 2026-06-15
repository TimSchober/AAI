"""
Central configuration for combined RAG API + Job Search Agent
"""
from __future__ import annotations

import os
from pathlib import Path
from dotenv import load_dotenv

PACKAGE_ROOT = Path(__file__).resolve().parent
REPO_ROOT = PACKAGE_ROOT

# Load env files
load_dotenv(REPO_ROOT / ".env")
load_dotenv(REPO_ROOT / ".env.example")

# ========== RAG API Configuration ==========
OLAMA_HOST: str = os.getenv("OLAMA_HOST", "http://localhost:11434")
OLAMA_MODEL: str = os.getenv("OLAMA_MODEL", "qwen3.5:4b")
DATABASE_URL: str = os.getenv("DATABASE_URL", "sqlite:///./rag.db")
FAISS_INDEX_PATH: str = os.getenv("FAISS_INDEX_PATH", "./data/index.faiss")
FAISS_META_PATH: str = os.getenv("FAISS_META_PATH", "./data/meta.json")
CHUNK_SIZE: int = int(os.getenv("CHUNK_SIZE", "500"))
CHUNK_OVERLAP: int = int(os.getenv("CHUNK_OVERLAP", "50"))
TOP_K: int = int(os.getenv("TOP_K", "4"))
HF_TIMEOUT: int = int(os.getenv("HF_TIMEOUT", "120"))

# ========== Job Agent Configuration ==========
OLLAMA_BASE_URL: str = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
OLLAMA_OPENAI_URL: str = f"{OLLAMA_BASE_URL.rstrip('/')}/v1"
OLLAMA_API_KEY: str = os.getenv("OLLAMA_API_KEY", "ollama")

# Arbeitsagentur API
JOBSUCHE_API_KEY: str = os.getenv("JOBSUCHE_API_KEY", "jobboerse-jobsuche")
JOBSUCHE_API_URL: str = os.getenv(
    "JOBSUCHE_API_URL",
    "https://rest.arbeitsagentur.de/jobboerse/jobsuche-service",
)

# ChromaDB (Job Agent RAG)
CHROMA_DB_PATH: str = os.getenv(
    "CHROMA_DB_PATH",
    str(REPO_ROOT / "ChromaDB" / "chroma_db"),
)
CHROMA_COLLECTION: str = os.getenv("CHROMA_COLLECTION", "bewerbungsunterlagen")
EMBED_MODEL: str = os.getenv("EMBED_MODEL", "all-MiniLM-L6-v2")
DOCS_DIR: str = os.getenv("DOCS_DIR", str(REPO_ROOT / "ChromaDB" / "docs"))

# ========== MCP Server Configuration ==========
MCP_HOST: str = os.getenv("MCP_HOST", "127.0.0.1")
MCP_PORT: int = int(os.getenv("MCP_PORT", "8000"))
MCP_PATH: str = os.getenv("MCP_PATH", "/mcp")
MCP_URL: str = os.getenv("MCP_URL", f"http://{MCP_HOST}:{MCP_PORT}{MCP_PATH}")

# ========== API Server Configuration ==========
API_HOST: str = os.getenv("API_HOST", "0.0.0.0")
API_PORT: int = int(os.getenv("API_PORT", "8000"))
API_RELOAD: bool = os.getenv("API_RELOAD", "false").lower() == "true"
