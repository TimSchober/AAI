"""
rag/vector_store.py
====================
ChromaDB Vektorspeicher für den Job Application Agent.

Unterstützte Dokument-Typen und ihre Tags:
  - lebenslauf     (.md)
  - motivation     (.md)
  - noten          (.md oder .pdf)
  - zeugnis        (.md)
  - praeferenz     (.json)  ← Stellenpräferenzen des Nutzers

Verwendung:
  store = JobApplicationStore()
  store.add_document("lebenslauf.md", doc_type="lebenslauf")
  results = store.query("Python Kenntnisse", doc_types=["lebenslauf"])
"""

import os
import json
import hashlib
from pathlib import Path
from datetime import datetime
from typing import Optional

import chromadb
from chromadb.utils import embedding_functions


# ─── Konfiguration ────────────────────────────────────────────────────────────

CHROMA_PATH   = "./chroma_db"          # Wo ChromaDB seine Daten speichert
COLLECTION    = "bewerbungsunterlagen" # Name der Collection
EMBED_MODEL   = "all-MiniLM-L6-v2"    # Schnelles Sentence-Transformer-Modell
                                       # Alternativ: "paraphrase-multilingual-MiniLM-L12-v2"
                                       # für besseres Deutsch-Verständnis

# Gültige Dokument-Typen (entsprechen euren Tags)
VALID_TYPES = {"lebenslauf", "motivation", "noten", "zeugnis", "praeferenz"}

# Chunk-Größe: wie viele Zeichen pro Chunk (überlappend)
CHUNK_SIZE    = 800
CHUNK_OVERLAP = 100


# ─── Hilfs-Funktionen ─────────────────────────────────────────────────────────

def _chunk_text(text: str, size: int = CHUNK_SIZE, overlap: int = CHUNK_OVERLAP) -> list[str]:
    """
    Teilt einen langen Text in überlappende Chunks.
    Überlappung verhindert, dass zusammenhängende Infos auseinandergerissen werden.
    """
    chunks = []
    start = 0
    while start < len(text):
        end = start + size
        chunks.append(text[start:end])
        start += size - overlap
    return [c.strip() for c in chunks if c.strip()]


def _read_file(path: str | Path) -> str:
    """
    Liest .md, .txt und .json Dateien aus.
    Für PDFs: hier einfach Platzhalter – echte PDF-Extraktion via pymupdf
    (siehe Kommentar unten).
    """
    path = Path(path)
    suffix = path.suffix.lower()

    if suffix in {".md", ".txt"}:
        return path.read_text(encoding="utf-8")

    elif suffix == ".json":
        data = json.loads(path.read_text(encoding="utf-8"))
        # JSON flach als lesbarer Text serialisieren
        return json.dumps(data, ensure_ascii=False, indent=2)

    elif suffix == ".pdf":
        # ── PDF-Extraktion (auskommentiert wegen Speicherplatz in Demo) ──────
        # import fitz  # pip install pymupdf
        # doc = fitz.open(str(path))
        # return "\n".join(page.get_text() for page in doc)
        raise NotImplementedError(
            "PDF-Unterstützung: 'pip install pymupdf' und Kommentar oben einkommentieren."
        )
    else:
        raise ValueError(f"Nicht unterstütztes Dateiformat: {suffix}")


def _doc_id(path: str, chunk_index: int) -> str:
    """Eindeutige ID pro Chunk: Hash aus Dateipfad + Chunk-Nummer."""
    base = hashlib.md5(str(path).encode()).hexdigest()[:8]
    return f"{base}_chunk{chunk_index}"


# ─── Hauptklasse ──────────────────────────────────────────────────────────────

class JobApplicationStore:
 
    def __init__(self, path: str = CHROMA_PATH):
        # Persistenter Client: Daten bleiben auf der Festplatte erhalten
        self.client = chromadb.PersistentClient(path=path)

        # Embedding-Funktion: lädt das Modell beim ersten Aufruf herunter (~90 MB)
        self.embed_fn = embedding_functions.SentenceTransformerEmbeddingFunction(
            model_name=EMBED_MODEL
        )

        # Collection holen oder neu anlegen
        self.collection = self.client.get_or_create_collection(
            name=COLLECTION,
            embedding_function=self.embed_fn,
            metadata={"hnsw:space": "cosine"},  # Cosine-Ähnlichkeit für Text
        )
        print(f"[Store] Collection '{COLLECTION}' bereit. "
              f"Aktuell {self.collection.count()} Chunks gespeichert.")

    # ── Dokumente hinzufügen ───────────────────────────────────────────────────

    def add_document(
        self,
        file_path: str | Path,
        doc_type: str,
        language: str = "de",
        extra_tags: Optional[dict] = None,
    ) -> int:
       
        """
        Liest eine Datei ein, chunked sie und speichert alle Chunks in ChromaDB.

        Args:
            file_path:  Pfad zur Datei (.md, .json, .pdf)
            doc_type:   Einer von VALID_TYPES (z.B. "lebenslauf")
            language:   Sprache des Dokuments ("de" oder "en")
            extra_tags: Optionale zusätzliche Metadaten, z.B. {"firma": "SAP"}

        Returns:
            Anzahl der eingefügten Chunks
        """
        if doc_type not in VALID_TYPES:
            raise ValueError(f"Ungültiger doc_type '{doc_type}'. Erlaubt: {VALID_TYPES}")

        path = Path(file_path)
        if not path.exists():
            raise FileNotFoundError(f"Datei nicht gefunden: {path}")

        text = _read_file(path)
        chunks = _chunk_text(text)

        # Metadaten für alle Chunks dieser Datei
        base_metadata = {
            "type":      doc_type,       # ← Haupt-Tag für gezielte Queries
            "language":  language,
            "source":    path.name,
            "added_at":  datetime.now().isoformat(),
        }
        if extra_tags:
            base_metadata.update(extra_tags)

        ids        = [_doc_id(path, i) for i in range(len(chunks))]
        metadatas  = [
            {**base_metadata, "chunk_index": i, "chunk_total": len(chunks)}
            for i in range(len(chunks))
        ]

        # Bereits vorhandene IDs überschreiben (upsert = update + insert)
        self.collection.upsert(
            ids=ids,
            documents=chunks,
            metadatas=metadatas,
        )
        print(f"[Store] '{path.name}' ({doc_type}) → {len(chunks)} Chunks gespeichert.")
        return len(chunks)

    def add_all_documents(self, docs_dir: str | Path) -> None:
        """
        Konvention: Liest alle Dateien aus einem Ordner anhand ihres Namens.

        Erwartete Dateinamen (Beispiele):
        lebenslauf.md, motivation.md, noten.md, zeugnis_sap.md, praeferenzen.json

        Der doc_type wird automatisch aus dem Dateinamen abgeleitet.
        """
        docs_dir = Path(docs_dir)
        name_to_type = {
            "lebenslauf":  "lebenslauf",
            "motivation":  "motivation",
            "noten":       "noten",
            "zeugnis":     "zeugnis",
            "praeferenz":  "praeferenz",
            "praeferenzen": "praeferenz",
        }
        for file in sorted(docs_dir.iterdir()):
            if file.suffix.lower() not in {".md", ".txt", ".json"}:
                continue
            # Dateinamen-Stem gegen bekannte Typen prüfen
            matched = next(
                (t for key, t in name_to_type.items() if key in file.stem.lower()),
                None
            )
            if matched:
                self.add_document(file, doc_type=matched)
            else:
                print(f"[Store] Übersprungen (kein passender Typ): {file.name}")

    # ── Abfragen ──────────────────────────────────────────────────────────────

    def query(
        self,
        query_text: str,
        doc_types: Optional[list[str]] = None,
        n_results: int = 5,
    ) -> list[dict]:
        """
        Semantische Suche in der Vektordatenbank.

        Args:
            query_text:  Natürlichsprachige Suchanfrage
            doc_types:   Optional: nur in diesen Typen suchen, z.B. ["lebenslauf"]
                         None = alle Dokumente durchsuchen
            n_results:   Wie viele Chunks zurückgeben

        Returns:
            Liste von Dicts mit 'text', 'score', 'type', 'source', 'chunk_index'
        """
        # ChromaDB where-Filter: nur bestimmte doc_types
        where = None
        if doc_types:
            if len(doc_types) == 1:
                where = {"type": doc_types[0]}
            else:
                where = {"$or": [{"type": t} for t in doc_types]}

        results = self.collection.query(
            query_texts=[query_text],
            n_results=min(n_results, self.collection.count() or 1),
            where=where,
            include=["documents", "metadatas", "distances"],
        )

        output = []
        for doc, meta, dist in zip(
            results["documents"][0],
            results["metadatas"][0],
            results["distances"][0],
        ):
            output.append({
                "text":        doc,
                "score":       round(1 - dist, 3),  # Cosine: 1 = identisch
                "type":        meta.get("type"),
                "source":      meta.get("source"),
                "chunk_index": meta.get("chunk_index"),
            })

        return output

    def get_profile_context(self, job_description: str) -> str:
        """
        Hilfsmethode für Agent 1:
        Holt die relevantesten Chunks aus Lebenslauf + Präferenzen
        und gibt sie als formatierten String zurück – direkt als Prompt-Kontext.
        """
        skills    = self.query(job_description, doc_types=["lebenslauf"], n_results=3)
        prefs     = self.query(job_description, doc_types=["praeferenz"],  n_results=2)
        zeugnisse = self.query(job_description, doc_types=["zeugnis"],     n_results=2)

        sections = []
        if skills:
            sections.append("## Relevante Lebenslauf-Abschnitte\n" +
                            "\n---\n".join(r["text"] for r in skills))
        if prefs:
            sections.append("## Stellenpräferenzen\n" +
                            "\n---\n".join(r["text"] for r in prefs))
        if zeugnisse:
            sections.append("## Arbeitszeugnisse\n" +
                            "\n---\n".join(r["text"] for r in zeugnisse))

        return "\n\n".join(sections)

    # ── Verwaltung ────────────────────────────────────────────────────────────

    def list_documents(self) -> dict:
        """Übersicht: wie viele Chunks pro doc_type sind gespeichert."""
        all_meta = self.collection.get(include=["metadatas"])["metadatas"]
        counts: dict[str, int] = {}
        for m in all_meta:
            t = m.get("type", "unbekannt")
            counts[t] = counts.get(t, 0) + 1
        return counts

    def delete_document_type(self, doc_type: str) -> None:
        """Löscht alle Chunks eines bestimmten Typs (z.B. um den Lebenslauf zu aktualisieren)."""
        self.collection.delete(where={"type": doc_type})
        print(f"[Store] Alle Chunks vom Typ '{doc_type}' gelöscht.")

    def reset(self) -> None:
        """Löscht die gesamte Collection (Vorsicht!)."""
        self.client.delete_collection(COLLECTION)
        print("[Store] Collection gelöscht.")
        