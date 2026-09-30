"""Build the curated internal CSV package for the Sondondo research team.

The package contains the current research inputs, safe linkage/family outputs,
and explicitly review-only candidate queues. It does not copy local archives,
temporary working files, or every intermediate model artifact.
"""

from __future__ import annotations

import csv
import shutil
from pathlib import Path

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
PACKAGE = ROOT / "research_data"

COPY_FILES = [
    ("data/raw/personas.csv", "01_source_personas.csv", "Source persona appearances used as the linkage input."),
    ("data/raw/bautismos_clean.csv", "01_baptisms_clean.csv", "Clean baptism-event source table."),
    ("data/raw/matrimonios_clean.csv", "01_marriages_clean.csv", "Clean marriage-event source table."),
    ("data/raw/entierros_clean.csv", "01_burials_clean.csv", "Clean burial-event source table."),
    ("data/raw/places.csv", "01_places.csv", "Available place reference table; not yet a general automatic linkage feature."),
    ("data/reviewed/name_frequency_analysis_v13.csv", "02_name_frequency_analysis_v13.csv", "Current reviewed name-frequency and rarity reference."),
    ("data/reviewed/approved_name_variant_mappings_v1.csv", "02_approved_name_variant_mappings_v1.csv", "Reviewed name-variant mappings used for matching support."),
    ("data/reviewed/persona_name_overrides_v1.csv", "02_persona_name_overrides_v1.csv", "Reviewed person-level source-name corrections."),
    ("data/reviewed/persona_gender_overrides_v1.csv", "02_persona_gender_overrides_v1.csv", "Reviewed person-level gender corrections."),
    ("data/reviewed/name_enhanced_candidate_review_labels_v2.csv", "02_name_enhanced_review_labels_v2.csv", "Completed reviewer decisions for name-enhanced candidates."),
    ("outputs/graph_imports/safe_family_release_v3/neo4j_people_nodes.csv", "04_safe_identity_people_nodes.csv", "Safe identity-level people for the trusted family graph."),
    ("outputs/graph_imports/safe_family_release_v3/neo4j_trusted_relationships.csv", "04_trusted_family_relationships.csv", "Trusted parent-child and spouse relationships only."),
    ("outputs/graph_imports/safe_family_release_v3/source_persona_membership_audit.csv", "04_source_persona_to_identity_and_family_audit.csv", "Trace from source personas to safe identity people and family clusters."),
    ("outputs/reports/securely_deduplicated_people_v1.csv", "05_securely_deduplicated_people.csv", "Secure multi-record people available for later restricted linkage work."),
    ("outputs/reports/securely_deduplicated_persona_evidence_v1.csv", "05_securely_deduplicated_persona_evidence.csv", "Source-persona evidence for securely deduplicated people."),
    ("outputs/review/splink_hybrid_v3_expanded_candidate_high_priority_review_v1.csv", "06_expanded_candidates_high_priority_review.csv", "Expanded candidates requiring priority human review; not merged."),
    ("outputs/review/splink_hybrid_v3_expanded_candidate_manual_review_v1.csv", "06_expanded_candidates_manual_review.csv", "Expanded candidates requiring manual review; not merged."),
    ("outputs/review/professor_potential_siblings_with_parents_v1.csv", "07_potential_siblings_with_parents_review.csv", "Sibling-discovery candidates from shared parents and the ±15-year rule; review-only."),
    ("outputs/review/professor_spouse_baptism_links_for_review_v1.csv", "07_spouse_baptism_links_review.csv", "Possible marriage-spouse and baptismal-child links; review-only."),
    ("outputs/reports/family_cluster_release_readiness_v3.csv", "08_family_cluster_release_readiness.csv", "Current safe family-release counts and validation gate."),
    ("outputs/reports/name_reference_validation_v1.csv", "08_name_reference_validation.csv", "Validation of reviewed rules and name-reference preparation."),
    ("outputs/reports/splink_hybrid_v3_expanded_candidate_scoring_summary_v1.csv", "08_expanded_candidate_scoring_summary.csv", "Summary of held expanded candidates and their review tiers."),
    ("outputs/reports/marriage_parent_pair_sibling_discovery_summary_v1.csv", "08_sibling_discovery_summary.csv", "Summary of the sibling-discovery review-only method."),
]

PARQUET_EXPORTS = [
    (
        "data/processed/identity_aware_family_cluster_membership_final_v3.parquet",
        "03_source_persona_safe_identity_family_membership_v3.csv",
        "Current source-persona membership with safe identity and family-cluster assignment.",
    ),
    (
        "data/processed/historical_person_entities_final_safe.parquet",
        "03_historical_person_entities_final_safe.csv",
        "Safe final identity entities used for the released linkage layer.",
    ),
]


def copy_file(source_relative: str, destination_name: str) -> int:
    source = ROOT / source_relative
    assert source.exists(), f"Missing required source file: {source}"
    destination = PACKAGE / destination_name
    shutil.copy2(source, destination)
    return destination.stat().st_size


def export_parquet(source_relative: str, destination_name: str) -> int:
    source = ROOT / source_relative
    assert source.exists(), f"Missing required source file: {source}"
    destination = PACKAGE / destination_name
    frame = pd.read_parquet(source)
    frame.to_csv(destination, index=False)
    return destination.stat().st_size


def main() -> None:
    PACKAGE.mkdir(parents=True, exist_ok=True)
    manifest_rows: list[dict[str, object]] = []

    for source, destination, description in COPY_FILES:
        size = copy_file(source, destination)
        manifest_rows.append(
            {
                "file_name": destination,
                "source_path": source,
                "content_type": "copied_csv",
                "purpose": description,
                "release_status": "safe_release" if destination.startswith(("03_", "04_", "05_", "08_")) else "input_or_review_material",
                "bytes": size,
            }
        )

    for source, destination, description in PARQUET_EXPORTS:
        size = export_parquet(source, destination)
        manifest_rows.append(
            {
                "file_name": destination,
                "source_path": source,
                "content_type": "parquet_to_csv",
                "purpose": description,
                "release_status": "safe_release",
                "bytes": size,
            }
        )

    with (PACKAGE / "MANIFEST.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(manifest_rows[0]))
        writer.writeheader()
        writer.writerows(manifest_rows)

    print(f"Created internal research package: {PACKAGE}")
    print(f"Files in manifest: {len(manifest_rows)}")
    print(f"Total data size: {sum(row['bytes'] for row in manifest_rows):,} bytes")


if __name__ == "__main__":
    main()
