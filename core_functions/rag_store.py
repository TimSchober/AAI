"""
RAG store. Saves Job findings and user data. For now, needs to be adjusted in the future.

Supported doc types and their tags:
- lebenslauf      (.md)            CV
- motivation      (.md)            cover letter
- noten           (.md / .pdf)     grades
- zeugnis         (.md)            references
- praeferenz      (.json)          the user's job-search preferences
- stellenangebot  (added at runtime) job offers found by the agent
- unternehmen     (added at runtime) employer profiles the research agent built
- anhang          (added at runtime) images the user sent through the chat
"""

from __future__ import annotations

import json
import hashlib
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

import chromadb
from chromadb.utils import embedding_functions

from config import (
    CHROMA_DB_PATH,
    CHROMA_HOST,
    CHROMA_PORT,
    CHROMA_COLLECTION,
    EMBED_MODEL,
    UPLOAD_DIR,
)

VALID_TYPES = {
    "anhang",
    "lebenslauf",
    "motivation",
    "noten",
    "zeugnis",
    "praeferenz",
    "stellenangebot",
    "unternehmen",
    "arbeitszeugnis",
    "abschlusszeugnis",
    "cv",
    "notenübersicht",
    "noten",
}

CHUNK_SIZE = 800
CHUNK_OVERLAP = 100

def _chunk_text(text: str, size: int = CHUNK_SIZE, overlap: int = CHUNK_OVERLAP) -> list[str]:
    chunks: list[str] = []
    start = 0
    while start < len(text):
        end = start + size
        chunks.append(text[start:end])
        start += size - overlap
    return [c.strip() for c in chunks if c.strip()]


def _read_file(path: str | Path) -> str:
    path = Path(path)
    suffix = path.suffix.lower()

    if suffix in {".md", ".txt"}:
        return path.read_text(encoding="utf-8")
    if suffix == ".json":
        data = json.loads(path.read_text(encoding="utf-8"))
        return json.dumps(data, ensure_ascii=False, indent=2)
    if suffix == ".pdf":
        import fitz  # pymupdf
        doc = fitz.open(str(path))
        return "\n".join(page.get_text() for page in doc)
    if suffix == ".csv":
        import csv
        rows = list(csv.DictReader(path.read_text(encoding="utf-8").splitlines()))
        return "\n".join(
            ", ".join(f"{k}: {v}" for k, v in row.items()) for row in rows
        )
    raise ValueError(f"Unsupported file format: {suffix}")


def _doc_id(path: str, chunk_index: int) -> str:
    base = hashlib.md5(str(path).encode()).hexdigest()[:8]
    return f"{base}_chunk{chunk_index}"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


class JobApplicationStore:

    def __init__(
        self,
        path: str = CHROMA_DB_PATH,
        collection: str = CHROMA_COLLECTION,
        embed_model: str = EMBED_MODEL,
        host: str = CHROMA_HOST,
        port: int = CHROMA_PORT,
    ):

        if host:
            self.client = chromadb.HttpClient(host=host, port=port)
        else:
            self.client = chromadb.PersistentClient(path=path)
        self.embed_fn = embedding_functions.SentenceTransformerEmbeddingFunction(
            model_name=embed_model
        )
        self.collection = self.client.get_or_create_collection(
            name=collection,
            embedding_function=self.embed_fn,
            metadata={"hnsw:space": "cosine"},
        )

    def add_document(
        self,
        file_path: str | Path,
        doc_type: str,
        language: str = "de",
        extra_tags: Optional[dict] = None,
    ) -> int:
        if doc_type not in VALID_TYPES:
            raise ValueError(f"Invalid doc_type '{doc_type}'. Allowed: {VALID_TYPES}")

        path = Path(file_path)
        if not path.exists():
            raise FileNotFoundError(f"File not found: {path}")

        text = _read_file(path)
        chunks = _chunk_text(text)

        base_metadata: dict[str, Any] = {
            "type": doc_type,
            "language": language,
            "source": path.name,
            "added_at": _now(),
        }
        if extra_tags:
            base_metadata.update(extra_tags)

        ids = [_doc_id(path, i) for i in range(len(chunks))]
        metadatas = [
            {**base_metadata, "chunk_index": i, "chunk_total": len(chunks)}
            for i in range(len(chunks))
        ]

        self.collection.upsert(ids=ids, documents=chunks, metadatas=metadatas)
        return len(chunks)

    def add_all_documents(self, docs_dir: str | Path) -> dict[str, int]:
        docs_dir = Path(docs_dir)
        name_to_type = {
            "lebenslauf": "lebenslauf",
            "motivation": "motivation",
            "noten": "noten",
            "zeugnis": "zeugnis",
            "praeferenz": "praeferenz",
            "praeferenzen": "praeferenz",
            "arbeitszeugnis": "arbeitszeugnis",
            "abschlusszeugnis": "abschlusszeugnis",
            "cv": "cv",
            "notenübersicht": "notenübersicht",
            "noten": "noten"
        }
        ingested: dict[str, int] = {}
        for file in sorted(docs_dir.iterdir()):
            if file.suffix.lower() not in {".md", ".txt", ".json", ".pdf", ".csv"}:
                continue
            matched = next(
                (t for key, t in name_to_type.items() if key in file.stem.lower()),
                None,
            )
            if matched:
                ingested[file.name] = self.add_document(file, doc_type=matched)
        return ingested

    def add_text(
        self,
        text: str,
        doc_type: str,
        source: str,
        language: str = "de",
        extra_tags: Optional[dict] = None,
    ) -> int:
        """
        Store raw text that did not come from a file on disk.
        """
        if doc_type not in VALID_TYPES:
            raise ValueError(f"Invalid doc_type '{doc_type}'. Allowed: {VALID_TYPES}")
        chunks = _chunk_text(text)
        if not chunks:
            return 0

        base_metadata: dict[str, Any] = {
            "type": doc_type,
            "language": language,
            "source": source,
            "added_at": _now(),
        }
        if extra_tags:
            base_metadata.update(extra_tags)

        self.collection.upsert(
            ids=[_doc_id(f"{doc_type}:{source}", i) for i in range(len(chunks))],
            documents=chunks,
            metadatas=[
                {**base_metadata, "chunk_index": i, "chunk_total": len(chunks)}
                for i in range(len(chunks))
            ],
        )
        return len(chunks)

    def add_image(
        self,
        filename: str,
        data: bytes,
        mime_type: str = "image/png",
        caption: str = "",
        doc_type: str = "anhang",
        upload_dir: str | Path = UPLOAD_DIR,
    ) -> dict[str, Any]:
        """Persist an uploaded image and index a searchable record for it."""
        directory = Path(upload_dir)
        directory.mkdir(parents=True, exist_ok=True)
        source = f"{hashlib.md5(data).hexdigest()[:8]}_{Path(filename).name}"
        path = directory / source
        path.write_bytes(data)

        text = "\n".join(
            line
            for line in (
                f"Bild-Anhang: {filename}",
                f"Format: {mime_type}",
                f"Kommentar des Nutzers: {caption}" if caption.strip() else "",
            )
            if line
        )
        chunks = self.add_text(
            text,
            doc_type=doc_type,
            source=source,
            extra_tags={"mime_type": mime_type, "path": str(path), "kind": "image"},
        )
        return {"source": source, "path": str(path), "stored": chunks}

    def add_jobs(self, jobs: list[dict], language: str = "de") -> int:
        if not jobs:
            return 0

        ids: list[str] = []
        documents: list[str] = []
        metadatas: list[dict[str, Any]] = []

        for job in jobs:
            refnr = str(job.get("referenznummer") or job.get("refnr") or "")
            if not refnr:
                # Fall back to a content hash if the API gave us no refnr.
                refnr = hashlib.md5(json.dumps(job, sort_keys=True).encode()).hexdigest()[:12]

            documents.append(_job_to_text(job))
            ids.append(f"job_{hashlib.md5(refnr.encode()).hexdigest()[:12]}")
            metadatas.append(
                {
                    "type": "stellenangebot",
                    "language": language,
                    "source": "arbeitsagentur",
                    "referenznummer": refnr,
                    "titel": str(job.get("titel", "")),
                    "arbeitgeber": str(job.get("arbeitgeber", "")),
                    "ort": str(job.get("ort", "")),
                    "added_at": _now(),
                }
            )

        self.collection.upsert(ids=ids, documents=documents, metadatas=metadatas)
        return len(documents)

    def add_company(self, name: str, text: str, language: str = "de", **tags: Any) -> int:
        """Store an employer profile researched for a job offer."""
        return self.add_text(
            text,
            doc_type="unternehmen",
            source=name,
            language=language,
            extra_tags={"arbeitgeber": name, **{k: str(v) for k, v in tags.items() if v}},
        )

    def list_employers(self, limit: int = 20) -> list[dict[str, Any]]:
        """The employers of the job offers in the store, newest first."""
        all_meta = self.collection.get(include=["metadatas"])["metadatas"] or []

        researched = {
            str(m.get("arbeitgeber", "")).casefold()
            for m in all_meta
            if m.get("type") == "unternehmen"
        }

        employers: dict[str, dict[str, Any]] = {}
        for meta in sorted(
            (m for m in all_meta if m.get("type") == "stellenangebot"),
            key=lambda m: str(m.get("added_at", "")),
            reverse=True,
        ):
            name = str(meta.get("arbeitgeber", "")).strip()
            if not name:
                continue
            entry = employers.setdefault(
                name,
                {
                    "arbeitgeber": name,
                    "ort": str(meta.get("ort", "")),
                    "stellen": 0,
                    "titel": [],
                    "recherchiert": name.casefold() in researched,
                },
            )
            entry["stellen"] += 1
            titel = str(meta.get("titel", "")).strip()
            if titel and titel not in entry["titel"]:
                entry["titel"].append(titel)

        return list(employers.values())[:limit]

    def query(
        self,
        query_text: str,
        doc_types: Optional[list[str]] = None,
        n_results: int = 5,
    ) -> list[dict]:
        where = None
        if doc_types:
            if len(doc_types) == 1:
                where = {"type": doc_types[0]}
            else:
                where = {"$or": [{"type": t} for t in doc_types]}

        count = self.collection.count()
        if count == 0:
            return []

        results = self.collection.query(
            query_texts=[query_text],
            n_results=min(n_results, count),
            where=where,
            include=["documents", "metadatas", "distances"],
        )

        output: list[dict] = []
        for doc, meta, dist in zip(
            results["documents"][0],
            results["metadatas"][0],
            results["distances"][0],
        ):
            output.append(
                {
                    "text": doc,
                    "score": round(1 - dist, 3),  # cosine: 1.0 == identical
                    "type": meta.get("type"),
                    "source": meta.get("source"),
                    "referenznummer": meta.get("referenznummer"),
                    "titel": meta.get("titel"),
                }
            )
        return output

    def get_profile_context(self, job_description: str) -> str:
        skills = self.query(job_description, doc_types=["lebenslauf"], n_results=3)
        prefs = self.query(job_description, doc_types=["praeferenz"], n_results=2)
        zeugnisse = self.query(job_description, doc_types=["zeugnis"], n_results=2)

        sections: list[str] = []
        if skills:
            sections.append(
                "## Relevante Lebenslauf-Abschnitte\n"
                + "\n---\n".join(r["text"] for r in skills)
            )
        if prefs:
            sections.append(
                "## Stellenpräferenzen\n" + "\n---\n".join(r["text"] for r in prefs)
            )
        if zeugnisse:
            sections.append(
                "## Arbeitszeugnisse\n" + "\n---\n".join(r["text"] for r in zeugnisse)
            )
        return "\n\n".join(sections)


    def list_documents(self) -> dict[str, int]:
        all_meta = self.collection.get(include=["metadatas"])["metadatas"]
        counts: dict[str, int] = {}
        for m in all_meta:
            t = m.get("type", "unbekannt")
            counts[t] = counts.get(t, 0) + 1
        return counts

    def delete_document_type(self, doc_type: str) -> None:
        self.collection.delete(where={"type": doc_type})

    def reset(self) -> None:
        self.client.delete_collection(self.collection.name)


def _job_to_text(job: dict) -> str:
    lines = [
        f"Stellentitel: {job.get('titel', '')}",
        f"Arbeitgeber: {job.get('arbeitgeber', '')}",
        f"Ort: {job.get('ort', '')}",
        f"Arbeitszeit: {job.get('arbeitszeit', '')}",
        f"Befristung: {job.get('befristung', '')}",
        f"Beschäftigungsgrad: {job.get('beschaeftigungsgrad', '')}",
        f"Veröffentlicht am: {job.get('veroeffentlicht_am', '')}",
        f"Referenznummer: {job.get('referenznummer', '')}",
    ]
    for key in ("text", "anforderung", "leistungen"):
        val = job.get(key)
        if val:
            lines.append(f"{key.capitalize()}: {val}")
    if job.get("url"):
        lines.append(f"Link: {job['url']}")
    return "\n".join(re.sub(r"\s+", " ", ln).strip() for ln in lines if ln.strip())
