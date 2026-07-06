"""Evaluate materialized knowledge graph edges against gold-standard relationships.

Usage:
------
    PERSISTENCE_BACKEND=postgres \
    DATABASE_URL=postgresql+psycopg://assetmind:assetmind@localhost:5432/assetmind \
    .venv/bin/python -m scripts.evaluate_graph
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

    root = Path(__file__).resolve().parents[3]
    gold_path = root / "data" / "benchmark" / "graph_gold.json"

    if not gold_path.exists():
        print(f"ERROR: Gold standard graph relations not found at {gold_path}")
        return 1

    with open(gold_path, "r", encoding="utf-8") as f:
        gold_edges = json.load(f)

    print("Evaluating materialized knowledge graph completeness...")
    
    tp = 0
    fn = 0

    with session_scope() as session:
        # Load all materialized KnowledgeEdges
        from app.db.models import KnowledgeEdge
        from sqlalchemy import select

        db_edges_rows = session.execute(select(KnowledgeEdge)).scalars().all()
        
        # Build set of materialized tuples
        # Format: (source_type:source_id, relation_type, target_type:target_id)
        # Note: the gold graph has namespaces like asset:<tag> and document:<filename>
        # Let's map target document IDs in the database to filenames to match gold targets!
        from app.db.models import Document, Asset
        
        doc_id_to_name = {
            doc.id: doc.original_filename
            for doc in session.execute(select(Document)).scalars().all()
        }
        asset_id_to_tag = {
            asset.id: asset.tag
            for asset in session.execute(select(Asset)).scalars().all()
        }

        db_relations = set()
        for edge in db_edges_rows:
            source_namespace = f"{edge.source_type}:{asset_id_to_tag.get(edge.source_id, edge.source_id)}"
            target_val = edge.target_id
            if edge.target_type == "document":
                target_val = doc_id_to_name.get(edge.target_id, edge.target_id)
            target_namespace = f"{edge.target_type}:{target_val}"
            
            db_relations.add((source_namespace.upper(), edge.relation_type.lower(), target_namespace.upper()))

        print(f"Loaded {len(db_relations)} materialized edges from database.")

        for gold in gold_edges:
            g_source = gold["source"].upper()
            g_relation = gold["relation_type"].lower()
            g_target = gold["target"].upper()
            
            gold_tuple = (g_source, g_relation, g_target)

            if gold_tuple in db_relations:
                tp += 1
            else:
                fn += 1
                print(f"  MISSING EDGE: {gold['source']} ─[{gold['relation_type']}]─> {gold['target']}")

    total_gold = len(gold_edges)
    completeness_score = (tp / total_gold) if total_gold > 0 else 0.0

    print("\nKnowledge Graph Completeness Summary:")
    print(f"  Total Gold Edges      : {total_gold}")
    print(f"  True Positives Found  : {tp}")
    print(f"  Missing Edges (FN)    : {fn}")
    print(f"  Completeness Score    : {completeness_score:.4f} ({completeness_score*100:.1f}%)")

    return 0

if __name__ == "__main__":
    sys.exit(main())
