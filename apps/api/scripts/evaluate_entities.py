"""Evaluate entity extraction precision, recall, and F1 score against gold-standard targets.

Usage:
------
    PERSISTENCE_BACKEND=postgres \
    DATABASE_URL=postgresql+psycopg://assetmind:assetmind@localhost:5432/assetmind \
    .venv/bin/python -m scripts.evaluate_entities
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

from app.core import config
from app.db.session import get_database_url, session_scope

# Force Postgres
config.settings.persistence_backend = "postgres"

def main() -> int:
    try:
        get_database_url()
    except Exception as exc:
        print(f"Database error: {exc}")
        return 1

    from app.db import repository as repo

    root = Path(__file__).resolve().parents[3]
    gold_path = root / "data" / "benchmark" / "entity_gold.json"

    if not gold_path.exists():
        print(f"ERROR: Gold standard entities not found at {gold_path}")
        return 1

    with open(gold_path, "r", encoding="utf-8") as f:
        gold_data = json.load(f)

    print("Evaluating entity extraction accuracy...")
    
    total_true_positives = 0
    total_false_positives = 0
    total_false_negatives = 0

    with session_scope() as session:
        # Load all documents from DB
        db_docs = repo.list_documents(session=session)
        for doc in db_docs:
            filename = doc["original_filename"]
            doc_id = doc["id"]

            if filename not in gold_data:
                continue

            gold_tags = {item["value"].upper() for item in gold_data[filename]}
            
            # Load extracted tags from DB for this document
            # Query extracted entities mapped to mentions in this document
            from app.db.models import AssetMention, ExtractedEntity
            from sqlalchemy import select
            
            entities = session.execute(
                select(ExtractedEntity.normalized_value)
                .join(AssetMention, AssetMention.entity_id == ExtractedEntity.id)
                .where(AssetMention.document_id == doc_id)
            ).scalars().all()
            
            extracted_tags = {tag.upper() for tag in entities if tag}

            tp = len(gold_tags.intersection(extracted_tags))
            fp = len(extracted_tags - gold_tags)
            fn = len(gold_tags - extracted_tags)

            total_true_positives += tp
            total_false_positives += fp
            total_false_negatives += fn

            print(f"  Document '{filename}':")
            print(f"    Expected tags   : {list(gold_tags)}")
            print(f"    Extracted tags  : {list(extracted_tags)}")
            print(f"    TP: {tp} | FP: {fp} | FN: {fn}")

    # Compute F1
    precision = (
        total_true_positives / (total_true_positives + total_false_positives)
        if (total_true_positives + total_false_positives) > 0
        else 0.0
    )
    recall = (
        total_true_positives / (total_true_positives + total_false_negatives)
        if (total_true_positives + total_false_negatives) > 0
        else 0.0
    )
    f1 = (
        (2 * precision * recall) / (precision + recall)
        if (precision + recall) > 0
        else 0.0
    )

    print("\nEntity Extraction Evaluation Summary:")
    print(f"  Precision: {precision:.4f} ({precision*100:.1f}%)")
    print(f"  Recall   : {recall:.4f} ({recall*100:.1f}%)")
    print(f"  F1 Score : {f1:.4f} ({f1*100:.1f}%)")

    return 0

if __name__ == "__main__":
    sys.exit(main())
