# 🤖 AAI: Multimodal RAG Agent + Job Search Platform

Alles-in-einem Projekt mit:
- **RAG API**: FastAPI für Dokumentenverarbeitung, FAISS Retrieval
- **Job Agent CLI**: Intelligenter Agent für Jobsuche

## 🚀 Quick Start

```bash
cd AAI/

# 1. venv aktivieren
source ../venv/bin/activate

# 2. Dependencies
pip install -r requirements.txt

# 3. .env setup
cp .env.example .env

# 4. Starten
python main.py              # RAG API (Standard)
python main.py --cli        # Job Agent CLI
python -m mcp_server        # MCP Server (optional)
python -m ingest            # ChromaDB Ingest
```

## 📚 RAG API Endpoints

```bash
# Health Check
curl http://localhost:8000/health

# Dokument hochladen
curl -X POST http://localhost:8000/ingest \
  -F "files=@document.pdf"

# Abfrage
curl -X POST http://localhost:8000/query \
  -F "q=Was steht darin?"

# Dokumente auflisten
curl http://localhost:8000/documents

# Index neu aufbauen
curl -X POST http://localhost:8000/rebuild-index
```

## 🎤 Job Agent CLI

```bash
python main.py --cli

# Dann Prompt eingeben:
# > Ich suche eine Stelle als Softwareentwickler in Berlin
```

## 📁 Struktur

```
AAI/
├── main.py                 # Hybrid Einstiegspunkt
├── config.py              # Zentrale Konfiguration
├── requirements.txt       # All Dependencies
├── api/
│   └── rag_routes.py      # RAG FastAPI Endpoints
├── agents/
│   ├── job_search_agent.py
│   └── __init__.py
├── core_functions/
├── mcp_server/
├── ChromaDB/
├── data/                  # FAISS Index
├── ingest.py
└── .env.example
```

## ⚙️ Konfiguration

Bearbeite `.env` für:
- Ollama Host & Model
- Database URL
- FAISS Pfade
- API Port

## 🔧 Troubleshooting

| Problem | Lösung |
|---------|--------|
| `ConnectionError: localhost:11434` | `ollama serve` |
| Port 8000 belegt | `.env`: `API_PORT=8001` |
| Import Error | Stellen Sie sicher, aus AAI/ Ordner zu starten |

---

**Status:** Ready to use! 🚀
