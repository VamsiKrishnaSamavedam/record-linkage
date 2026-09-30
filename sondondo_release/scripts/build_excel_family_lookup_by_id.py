"""Build an Excel-friendly, read-only family-cluster lookup by identity ID."""

from pathlib import Path

import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parents[1]
INPUT_PATH = PROJECT_ROOT / "outputs" / "review" / "family_cluster_lookup_final_v3.csv"
OUTPUT_PATH = PROJECT_ROOT / "outputs" / "review" / "family_cluster_person_lookup_by_id_v1.csv"
SUMMARY_PATH = PROJECT_ROOT / "outputs" / "reports" / "family_cluster_person_lookup_by_id_summary_v1.csv"


def main() -> None:
    people = pd.read_csv(INPUT_PATH, dtype={"identity_person_id": "string", "family_cluster_id": "string"})
    required = {
        "identity_person_id", "family_cluster_id", "preferred_name", "gender", "earliest_year", "latest_year",
        "roles", "source_persona_count", "safe_persona_count", "family_cluster_release_status",
    }
    missing = required - set(people.columns)
    if missing:
        raise KeyError(f"Missing expected lookup columns: {sorted(missing)}")
    if people["identity_person_id"].duplicated().any():
        raise ValueError("Input contains duplicate identity_person_id values.")

    cluster_sizes = people.groupby("family_cluster_id")["identity_person_id"].size().rename("family_cluster_member_count")
    lookup = people[["identity_person_id", "family_cluster_id", "preferred_name"]].rename(columns={
        "identity_person_id": "lookup_identity_person_id",
        "preferred_name": "lookup_preferred_name",
    })
    members = people.rename(columns={
        "identity_person_id": "related_identity_person_id",
        "preferred_name": "related_preferred_name",
        "gender": "related_gender",
        "earliest_year": "related_earliest_year",
        "latest_year": "related_latest_year",
        "roles": "related_roles",
        "source_persona_count": "related_source_persona_count",
        "safe_persona_count": "related_safe_persona_count",
        "family_cluster_release_status": "related_release_status",
    })
    output = lookup.merge(members, on="family_cluster_id", how="inner", validate="m:m")
    output["family_cluster_member_count"] = output["family_cluster_id"].map(cluster_sizes).astype(int)
    output["is_lookup_person"] = output["lookup_identity_person_id"].eq(output["related_identity_person_id"])
    output["relationship_scope"] = "same_trusted_family_cluster"
    output = output[[
        "lookup_identity_person_id", "lookup_preferred_name", "family_cluster_id", "family_cluster_member_count",
        "related_identity_person_id", "related_preferred_name", "related_gender", "related_earliest_year",
        "related_latest_year", "related_roles", "related_source_persona_count", "related_safe_persona_count",
        "related_release_status", "is_lookup_person", "relationship_scope",
    ]].sort_values(["lookup_identity_person_id", "is_lookup_person", "related_preferred_name"], ascending=[True, False, True])

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    SUMMARY_PATH.parent.mkdir(parents=True, exist_ok=True)
    output.to_csv(OUTPUT_PATH, index=False, encoding="utf-8")
    summary = pd.DataFrame([
        {"metric": "lookup_identity_people", "value": people["identity_person_id"].nunique()},
        {"metric": "family_clusters", "value": people["family_cluster_id"].nunique()},
        {"metric": "lookup_result_rows", "value": len(output)},
        {"metric": "relationship_scope", "value": "same_trusted_family_cluster"},
    ])
    summary.to_csv(SUMMARY_PATH, index=False)
    print(summary.to_string(index=False))
    print(f"Lookup: {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
