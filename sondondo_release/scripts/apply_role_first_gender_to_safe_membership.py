"""Apply the validated role-first gender result to the safe membership file.

This is a one-time, auditable data update.  It preserves every original column
except ``gender_clean`` and saves an untouched backup before making the update.
"""

from pathlib import Path
import shutil

import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parents[1]
PROCESSED_DIR = PROJECT_ROOT / "data" / "processed"
REPORT_DIR = PROJECT_ROOT / "outputs" / "reports"

TARGET_PATH = PROCESSED_DIR / "identity_cluster_membership_final_safe.parquet"
SOURCE_PATH = PROCESSED_DIR / "identity_cluster_membership_gender_enriched_v1.parquet"
BACKUP_PATH = PROCESSED_DIR / "archive" / "identity_cluster_membership_final_safe_before_gender_enrichment_v1.parquet"
AUDIT_PATH = REPORT_DIR / "identity_cluster_gender_offline_apply_audit_v1.csv"


def require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def main() -> None:
    require(TARGET_PATH.exists(), f"Missing safe membership target: {TARGET_PATH}")
    require(SOURCE_PATH.exists(), f"Missing validated gender source: {SOURCE_PATH}")
    BACKUP_PATH.parent.mkdir(parents=True, exist_ok=True)
    REPORT_DIR.mkdir(parents=True, exist_ok=True)

    original = pd.read_parquet(TARGET_PATH)
    enriched = pd.read_parquet(SOURCE_PATH)
    required_original = {"persona_idno", "gender_clean"}
    required_enriched = {"persona_idno", "gender_linkage_resolved"}
    require(required_original.issubset(original.columns), "Target is missing required columns.")
    require(required_enriched.issubset(enriched.columns), "Validated source is missing required columns.")
    require(original["persona_idno"].is_unique, "Target contains duplicate persona IDs.")
    require(enriched["persona_idno"].is_unique, "Validated source contains duplicate persona IDs.")
    require(
        set(original["persona_idno"]) == set(enriched["persona_idno"]),
        "Target and validated source do not contain the same persona IDs.",
    )

    if BACKUP_PATH.exists():
        backup = pd.read_parquet(BACKUP_PATH)
        require(len(backup) == len(original), "Existing backup has an unexpected row count.")
        require(
            set(backup["persona_idno"]) == set(original["persona_idno"]),
            "Existing backup does not match the target persona set.",
        )
    else:
        shutil.copy2(TARGET_PATH, BACKUP_PATH)
        backup = original.copy()

    resolved = enriched.set_index("persona_idno")["gender_linkage_resolved"]
    updated = original.copy()
    updated["gender_clean"] = updated["persona_idno"].map(resolved).fillna("unknown").astype("string")

    require(len(updated) == len(original), "Update changed the row count.")
    require(updated["persona_idno"].equals(original["persona_idno"]), "Update changed persona order or IDs.")
    non_gender_columns = [column for column in original.columns if column != "gender_clean"]
    require(
        updated[non_gender_columns].equals(original[non_gender_columns]),
        "A column other than gender_clean changed during the update.",
    )
    require(updated["gender_clean"].notna().all(), "Updated gender_clean contains nulls.")

    updated.to_parquet(TARGET_PATH, index=False)

    reloaded = pd.read_parquet(TARGET_PATH)
    require(len(reloaded) == len(original), "Saved target has an unexpected row count.")
    require(reloaded["persona_idno"].equals(original["persona_idno"]), "Saved target changed persona IDs.")
    require(
        reloaded[non_gender_columns].equals(original[non_gender_columns]),
        "Saved target changed a column other than gender_clean.",
    )

    before = original["gender_clean"].fillna("").astype("string").str.strip()
    after = reloaded["gender_clean"].fillna("").astype("string").str.strip().str.lower()
    audit = pd.DataFrame(
        [
            {"metric": "rows_preserved", "value": int(len(reloaded) == len(original))},
            {"metric": "persona_ids_preserved", "value": int(reloaded["persona_idno"].equals(original["persona_idno"]))},
            {"metric": "original_blank_or_unknown_gender_rows", "value": int(before.isin(["", "unknown", "nan"]).sum())},
            {"metric": "updated_male_rows", "value": int((after == "male").sum())},
            {"metric": "updated_female_rows", "value": int((after == "female").sum())},
            {"metric": "updated_unknown_rows", "value": int((after == "unknown").sum())},
            {"metric": "other_columns_preserved", "value": 1},
        ]
    )
    audit.to_csv(AUDIT_PATH, index=False)
    print(audit.to_string(index=False))
    print(f"Backup: {BACKUP_PATH}")
    print(f"Updated target: {TARGET_PATH}")
    print(f"Audit: {AUDIT_PATH}")


if __name__ == "__main__":
    main()
