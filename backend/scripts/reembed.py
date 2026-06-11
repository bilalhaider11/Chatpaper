#!/usr/bin/env python3
"""
Re-embed all files whose DocumentParent rows were embedded with a different model
than the one currently configured in settings.openai_embedding_model.

Safe to re-run: ChromaDB upsert is idempotent. Existing vectors for each file are
deleted before re-embedding so there are no duplicate or mixed-model vectors left behind.

Usage:
    cd backend
    python scripts/reembed.py [--dry-run]
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

# Make backend package importable when run as a script.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from core.chroma import delete_vectors_for_file, get_child_chunks_collection
from core.config import settings
from core.database import SessionLocal
from core.llm import get_embedder
from models.file_model import FileRecord
from models.ingestion import DocumentParent


def _child_texts(content: str) -> list[str]:
    from langchain_text_splitters import RecursiveCharacterTextSplitter
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=settings.child_chunk_size,
        chunk_overlap=settings.child_chunk_overlap,
    )
    return splitter.split_text(content) or [content]


def _embed_file(
    file_record: FileRecord,
    parents: list[DocumentParent],
    embedder: object,
    collection: object,
    dry_run: bool,
) -> None:
    file_id = file_record.id
    user_id = file_record.user_id
    file_hash = file_record.file_hash or ""

    print(f"  [{'DRY-RUN' if dry_run else 'RE-EMBED'}] file_id={file_id} ({file_record.filename})")

    if dry_run:
        return

    try:
        delete_vectors_for_file(file_id, user_id)
    except Exception as exc:
        print(f"  [WARN] ChromaDB delete failed for file {file_id}: {exc} — continuing")

    for parent in parents:
        children = _child_texts(parent.content)
        parent_id = parent.id
        child_ids = [f"{parent_id}:{i}" for i in range(len(children))]
        child_metas = [
            {
                "file_id": file_id,
                "user_id": user_id,
                "parent_id": parent_id,
                "child_index": i,
                "chunk_index": parent.chunk_index,
                "page_start": parent.page_start,
                "page_end": parent.page_end,
                "element_types": ",".join(parent.element_types) if parent.element_types else "",
                "file_hash": file_hash,
                "filename": file_record.filename,
                "file_type": file_record.file_type or "",
                "language": file_record.language or "unknown",
            }
            for i in range(len(children))
        ]

        for batch_start in range(0, len(children), settings.embedding_batch_size):
            batch_texts = children[batch_start: batch_start + settings.embedding_batch_size]
            batch_ids = child_ids[batch_start: batch_start + settings.embedding_batch_size]
            batch_metas = child_metas[batch_start: batch_start + settings.embedding_batch_size]
            embeddings = embedder.embed_documents(batch_texts)
            collection.upsert(
                ids=batch_ids,
                documents=batch_texts,
                embeddings=embeddings,
                metadatas=batch_metas,
            )


def main(dry_run: bool) -> None:
    current_model = settings.openai_embedding_model
    print(f"Target embedding model: {current_model}")
    if dry_run:
        print("DRY-RUN mode — no changes will be written.\n")

    db = SessionLocal()
    try:
        stale_file_ids: list[int] = [
            row.file_id
            for row in (
                db.query(DocumentParent.file_id)
                .filter(DocumentParent.embedding_model != current_model)
                .distinct()
                .all()
            )
        ]

        if not stale_file_ids:
            print("No files need re-embedding. All up to date.")
            return

        print(f"Found {len(stale_file_ids)} file(s) needing re-embedding.\n")

        embedder = get_embedder()
        collection = get_child_chunks_collection()

        for file_id in stale_file_ids:
            file_record = db.query(FileRecord).filter(FileRecord.id == file_id).first()
            if file_record is None:
                print(f"  [SKIP] file_id={file_id}: FileRecord not found")
                continue

            parents = db.query(DocumentParent).filter(DocumentParent.file_id == file_id).all()
            if not parents:
                print(f"  [SKIP] file_id={file_id}: no DocumentParent rows")
                continue

            _embed_file(file_record, parents, embedder, collection, dry_run)

            if not dry_run:
                for parent in parents:
                    parent.embedding_model = current_model
                    parent.is_committed = True
                file_record.embedding_model = current_model
                db.commit()
                print(f"  [DONE] file_id={file_id} — {len(parents)} parent(s) re-embedded")

        print("\nRe-embedding complete.")
    finally:
        db.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Re-embed stale document vectors.")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print which files would be re-embedded without making any changes.",
    )
    args = parser.parse_args()
    main(dry_run=args.dry_run)
