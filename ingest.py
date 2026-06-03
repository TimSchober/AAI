#!/usr/bin/env python3
"""
Helper to load the users personal documents (CV, motivation,
preferences and others) into the ChromaDB knowledge base.
"""

# TODO: Automate in the future and remove this helper.

from __future__ import annotations

import sys

from config import DOCS_DIR
from core_functions.rag_store import JobApplicationStore


def main() -> None:
    docs_dir = sys.argv[1] if len(sys.argv) > 1 else DOCS_DIR
    store = JobApplicationStore()
    print(f"Ingesting documents from: {docs_dir}")
    ingested = store.add_all_documents(docs_dir)
    if not ingested:
        print("No matching documents found.")
    else:
        for name, chunks in ingested.items():
            print(f"- {name}: {chunks} chunks")
    print("\nKnowledge base contents:")
    for doc_type, count in store.list_documents().items():
        print(f"  {doc_type}: {count} chunks")


if __name__ == "__main__":
    main()
