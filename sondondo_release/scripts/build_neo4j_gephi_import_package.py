"""Create a safe, read-only Neo4j and Gephi import package.

The graph contains one node per final identity person and only trusted family
relationships.  Review-only candidate links are deliberately excluded.
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parents[1]
PROCESSED_DIR = PROJECT_ROOT / "data" / "processed"
EXPORT_DIR = PROJECT_ROOT / "outputs" / "graph_imports" / "safe_family_release_v3"
REPORT_DIR = PROJECT_ROOT / "outputs" / "reports"

PEOPLE_PATH = PROCESSED_DIR / "family_cluster_people_final_v3.parquet"
RELATIONSHIPS_PATH = PROCESSED_DIR / "family_graph_relationships_trusted.parquet"
MEMBERSHIP_PATH = PROCESSED_DIR / "identity_aware_family_cluster_membership_final_v3.parquet"


def require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def text_column(series: pd.Series) -> pd.Series:
    return series.fillna("").astype("string").str.strip()


def first_present(frame: pd.DataFrame, choices: list[str]) -> str:
    for column in choices:
        if column in frame.columns:
            return column
    raise KeyError(f"None of these required columns exists: {choices}")


def main() -> None:
    for path in [PEOPLE_PATH, RELATIONSHIPS_PATH, MEMBERSHIP_PATH]:
        require(path.exists(), f"Missing required final-release file: {path}")
    EXPORT_DIR.mkdir(parents=True, exist_ok=True)
    REPORT_DIR.mkdir(parents=True, exist_ok=True)

    people = pd.read_parquet(PEOPLE_PATH).copy()
    relationships = pd.read_parquet(RELATIONSHIPS_PATH).copy()
    membership = pd.read_parquet(MEMBERSHIP_PATH).copy()

    person_id = first_present(people, ["identity_person_id", "person_id"])
    cluster_id = first_present(people, ["family_cluster_id"])
    name = first_present(people, ["preferred_name", "full_name_clean"])
    gender = first_present(people, ["gender", "gender_clean"])
    earliest = first_present(people, ["earliest_year"])
    latest = first_present(people, ["latest_year"])
    roles = first_present(people, ["roles"])
    source_persona_count = first_present(people, ["source_persona_count"])
    safe_persona_count = first_present(people, ["safe_persona_count"])

    people[person_id] = text_column(people[person_id])
    require(people[person_id].ne("").all(), "Final people table has blank person IDs.")
    require(people[person_id].is_unique, "Final people table has duplicate person IDs.")

    node_columns = [person_id, cluster_id, name, gender, earliest, latest, roles, source_persona_count, safe_persona_count]
    nodes = people[node_columns].copy()
    nodes.columns = [
        "person_id:ID(Person)",
        "family_cluster_id",
        "preferred_name",
        "gender",
        "earliest_year:INT",
        "latest_year:INT",
        "roles",
        "source_persona_count:INT",
        "safe_persona_count:INT",
    ]
    nodes["identity_person_id"] = nodes["person_id:ID(Person)"]
    nodes[":LABEL"] = "Person"
    nodes.to_csv(EXPORT_DIR / "neo4j_people_nodes.csv", index=False, encoding="utf-8")

    source = first_present(relationships, ["source_person_id", "source_identity_person_id"])
    target = first_present(relationships, ["target_person_id", "target_identity_person_id"])
    relation_type = first_present(relationships, ["relationship_type"])
    relationships[source] = text_column(relationships[source])
    relationships[target] = text_column(relationships[target])
    require(relationships[source].ne("").all() and relationships[target].ne("").all(), "Trusted relationships have blank endpoints.")
    known_people = set(people[person_id])
    missing_endpoints = (set(relationships[source]) | set(relationships[target])) - known_people
    require(not missing_endpoints, f"Trusted relationships reference people absent from node export: {sorted(missing_endpoints)[:10]}")

    optional = [column for column in ["evidence_count", "earliest_year", "latest_year", "relationship_id"] if column in relationships.columns]
    edges = relationships[[source, target, relation_type, *optional]].copy()
    edges = edges.rename(columns={
        source: ":START_ID(Person)",
        target: ":END_ID(Person)",
        relation_type: ":TYPE",
        "evidence_count": "evidence_count:INT",
        "earliest_year": "earliest_year:INT",
        "latest_year": "latest_year:INT",
    })
    edges[":TYPE"] = text_column(edges[":TYPE"]).str.upper().str.replace(r"[^A-Z0-9_]", "_", regex=True)
    edges.to_csv(EXPORT_DIR / "neo4j_trusted_relationships.csv", index=False, encoding="utf-8")

    gephi_nodes = nodes.rename(columns={
        "person_id:ID(Person)": "Id",
        "preferred_name": "Label",
        "earliest_year:INT": "earliest_year",
        "latest_year:INT": "latest_year",
        "source_persona_count:INT": "source_persona_count",
        "safe_persona_count:INT": "safe_persona_count",
    })[[
        "Id", "Label", "identity_person_id", "family_cluster_id", "gender", "earliest_year", "latest_year",
        "roles", "source_persona_count", "safe_persona_count"
    ]].copy()
    gephi_nodes.to_csv(EXPORT_DIR / "gephi_nodes.csv", index=False, encoding="utf-8")
    gephi_edges = edges.rename(columns={
        ":START_ID(Person)": "Source", ":END_ID(Person)": "Target", ":TYPE": "Type",
        "evidence_count:INT": "evidence_count", "earliest_year:INT": "earliest_year", "latest_year:INT": "latest_year",
    }).copy()
    gephi_edges["Type"] = "Directed"
    gephi_edges["relationship_type"] = text_column(relationships[relation_type]).str.lower().to_numpy()
    gephi_edges.to_csv(EXPORT_DIR / "gephi_edges.csv", index=False, encoding="utf-8")

    audit_columns = [column for column in ["persona_idno", "identity_person_id", "family_cluster_id", "full_name_clean", "event_identifier", "event_year", "event_role", "gender_clean", "family_cluster_release_status"] if column in membership.columns]
    audit = membership[audit_columns].copy()
    audit.to_csv(EXPORT_DIR / "source_persona_membership_audit.csv", index=False, encoding="utf-8")

    merged_people = people[people[source_persona_count].fillna(0).astype(int).gt(1)].copy()
    merged_people_report = merged_people[[
        person_id, cluster_id, name, gender, earliest, latest, roles, source_persona_count, safe_persona_count
    ]].rename(columns={
        person_id: "identity_person_id",
        name: "preferred_name",
        gender: "gender",
        earliest: "earliest_year",
        latest: "latest_year",
        roles: "roles",
    })
    merged_people_report.to_csv(REPORT_DIR / "securely_deduplicated_people_v1.csv", index=False, encoding="utf-8")

    merged_evidence_columns = [column for column in [
        "persona_idno", "identity_person_id", "family_cluster_id", "full_name_clean", "event_identifier",
        "event_year", "event_role", "gender_clean", "identity_cluster_source"
    ] if column in membership.columns]
    merged_evidence = membership[membership["identity_person_id"].isin(set(merged_people[person_id]))][merged_evidence_columns].copy()
    merged_evidence = merged_evidence.merge(
        merged_people[[person_id, source_persona_count]].rename(columns={person_id: "identity_person_id"}),
        on="identity_person_id", how="left", validate="m:1"
    )
    merged_evidence.to_csv(REPORT_DIR / "securely_deduplicated_persona_evidence_v1.csv", index=False, encoding="utf-8")

    safe_mask = membership["identity_cluster_source"].eq("safe_final_identity_cluster")
    dedup_summary = pd.DataFrame([
        {"metric": "original_persona_appearances", "value": len(membership)},
        {"metric": "safe_identity_personas", "value": int(safe_mask.sum())},
        {"metric": "safe_identity_people", "value": int(membership.loc[safe_mask, "identity_person_id"].nunique())},
        {"metric": "securely_merged_multi_record_people", "value": len(merged_people)},
        {"metric": "original_personas_in_secure_merges", "value": int(merged_people[source_persona_count].sum())},
        {"metric": "duplicate_persona_appearances_consolidated", "value": int(merged_people[source_persona_count].sum() - len(merged_people))},
        {"metric": "largest_secure_identity_group", "value": int(merged_people[source_persona_count].max())},
        {"metric": "provisional_singleton_personas_excluded_from_merges", "value": int((~safe_mask).sum())},
    ])
    dedup_summary.to_csv(REPORT_DIR / "secure_deduplication_summary_v1.csv", index=False, encoding="utf-8")

    summary = pd.DataFrame([
        {"metric": "unique_people_nodes", "value": len(nodes)},
        {"metric": "trusted_relationship_edges", "value": len(edges)},
        {"metric": "family_clusters", "value": people[cluster_id].nunique()},
        {"metric": "source_persona_audit_rows", "value": len(audit)},
        {"metric": "review_only_candidate_links_excluded", "value": 1},
    ])
    summary.to_csv(EXPORT_DIR / "import_package_summary.csv", index=False, encoding="utf-8")

    guide = """# Safe Family Release v3 — Neo4j and Gephi Import\n\nThis package contains the safe final identity people and trusted family relationships only.\nReview-only godparent and sibling candidates are deliberately excluded.\n\n## Neo4j Desktop\n1. Create a local database in Neo4j Desktop and open its Data Importer.\n2. Add `neo4j_people_nodes.csv` as a node file.  Use `person_id:ID(Person)` as the node ID and `:LABEL` as the label.\n3. Add `neo4j_trusted_relationships.csv` as a relationship file.  Map `:START_ID(Person)` and `:END_ID(Person)` to Person IDs, and use `:TYPE` as the relationship type.\n4. Run the import.  In Neo4j Browser, try:\n   `MATCH (p:Person {family_cluster_id: 'FCL-000001'})-[r]-(relative) RETURN p, r, relative LIMIT 200`\n   Replace the sample FCL with one from the node CSV.\n\n## Gephi\n1. Create a new project.  Import `gephi_nodes.csv` as Nodes and select `Id` as the identifier.\n2. Import `gephi_edges.csv` as Edges; map `Source`, `Target`, and `Type`.\n3. Use the Appearance panel to color nodes by `family_cluster_id`; size nodes by degree.\n4. For a readable tree, filter to a single `family_cluster_id` before applying a layout.\n\n## Audit file\n`source_persona_membership_audit.csv` is not a graph import. It provides the complete 47,072-row source-persona trace back to identity people and FCLs.\n"""
    guide = guide.replace("FCL-000001", "FCL2-000001").replace(
        "Replace the sample FCL with one from the node CSV.",
        "Replace the sample FCL with any actual value from the node CSV.",
    )
    (EXPORT_DIR / "README.md").write_text(guide, encoding="utf-8")

    print(summary.to_string(index=False))
    print(f"Created import package: {EXPORT_DIR}")


if __name__ == "__main__":
    main()
