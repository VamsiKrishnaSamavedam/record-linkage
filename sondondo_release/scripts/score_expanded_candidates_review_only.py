"""Score the newly expanded PRL candidates with the locked model.

The new marriage-godparent candidate rule improves retrieval, but it does not
provide labels.  Therefore this utility is deliberately review-only: it scores
every new candidate and produces ranked queues without altering identity IDs,
clusters, or the existing guarded automatic-match release.
"""

from __future__ import annotations

import copy
import json
import tempfile
from pathlib import Path

import duckdb
import pandas as pd
from splink import DuckDBAPI, Linker


PROJECT_ROOT = Path(__file__).resolve().parents[1]
INTERIM_DIR = PROJECT_ROOT / "data" / "interim"
PROCESSED_DIR = PROJECT_ROOT / "data" / "processed"
REPORT_DIR = PROJECT_ROOT / "outputs" / "reports"
REVIEW_DIR = PROJECT_ROOT / "outputs" / "review"
MODEL_DIR = PROJECT_ROOT / "outputs" / "models"

CONTEXT_PATH = INTERIM_DIR / "persona_context_name_enriched_v1.parquet"
EVIDENCE_PATH = PROCESSED_DIR / "name_enhanced_candidate_pair_evidence_v2.parquet"
MODEL_PATH = MODEL_DIR / "splink_hybrid_v3_development_model.json"
SCORED_PATH = PROCESSED_DIR / "splink_hybrid_v3_expanded_candidate_scores_v1.parquet"
HIGH_PRIORITY_PATH = REVIEW_DIR / "splink_hybrid_v3_expanded_candidate_high_priority_review_v1.csv"
MANUAL_REVIEW_PATH = REVIEW_DIR / "splink_hybrid_v3_expanded_candidate_manual_review_v1.csv"
SUMMARY_PATH = REPORT_DIR / "splink_hybrid_v3_expanded_candidate_scoring_summary_v1.csv"

MODEL_FIELDS = [
    "persona_idno", "event_key", "event_type", "role_standard",
    "full_name_clean", "parent_pair_clean", "spouse_name_clean_ctx",
    "child_name_clean_ctx", "event_place_clean", "event_year",
]


def require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def main() -> None:
    for directory in [PROCESSED_DIR, REPORT_DIR, REVIEW_DIR]:
        directory.mkdir(parents=True, exist_ok=True)
    for path in [CONTEXT_PATH, EVIDENCE_PATH, MODEL_PATH]:
        require(path.exists(), f"Missing required input: {path}")

    evidence = pd.read_parquet(EVIDENCE_PATH).copy()
    required_evidence = {
        "pair_key", "persona_id_l", "persona_id_r", "review_support_score",
        "gender_evidence_conflict", "chronology_review_flag", "same_event_same_role",
    }
    require(required_evidence.issubset(evidence.columns), "Expanded evidence is missing required safeguards.")
    require(evidence["pair_key"].is_unique, "Expanded evidence contains duplicate pair keys.")
    require(~evidence["gender_evidence_conflict"].astype(bool).any(), "Unsafe gender-conflict pairs reached expanded scoring.")
    require(~evidence["chronology_review_flag"].astype(bool).any(), "Unsafe chronology pairs reached expanded scoring.")
    require(~evidence["same_event_same_role"].astype(bool).any(), "Unsafe same-event/same-role pairs reached expanded scoring.")

    personas = pd.read_parquet(CONTEXT_PATH, columns=MODEL_FIELDS).copy()
    personas["persona_idno"] = personas["persona_idno"].astype(str)
    require(personas["persona_idno"].is_unique, "Enriched context has duplicate persona IDs.")
    personas["event_year"] = pd.to_numeric(personas["event_year"], errors="coerce")
    for column in [field for field in MODEL_FIELDS if field not in {"persona_idno", "event_year"}]:
        personas[column] = personas[column].fillna("").astype(str).str.strip()

    pairs = evidence[["pair_key", "persona_id_l", "persona_id_r"]].copy()
    pairs["persona_id_l"] = pairs["persona_id_l"].astype(str)
    pairs["persona_id_r"] = pairs["persona_id_r"].astype(str)
    require(set(pairs["persona_id_l"]).issubset(set(personas["persona_idno"])), "A left candidate persona is missing from context.")
    require(set(pairs["persona_id_r"]).issubset(set(personas["persona_idno"])), "A right candidate persona is missing from context.")

    with MODEL_PATH.open("r", encoding="utf-8") as handle:
        trained_settings = json.load(handle)

    with tempfile.TemporaryDirectory(prefix="sondondo_expanded_scoring_") as temp_dir:
        connection = duckdb.connect(str(Path(temp_dir) / "expanded_candidates.duckdb"))
        try:
            connection.register("personas_df", personas)
            connection.register("pairs_df", pairs)
            connection.execute("CREATE TABLE scoring_personas AS SELECT * FROM personas_df")
            connection.execute("CREATE TABLE candidate_core AS SELECT pair_key AS candidate_pair_id, persona_id_l AS persona_id_low, persona_id_r AS persona_id_high FROM pairs_df")
            connection.execute("CREATE TABLE candidate_left AS SELECT c.candidate_pair_id || '||L' AS splink_row_id, c.candidate_pair_id, p.* FROM candidate_core c INNER JOIN scoring_personas p ON c.persona_id_low = CAST(p.persona_idno AS VARCHAR)")
            connection.execute("CREATE TABLE candidate_right AS SELECT c.candidate_pair_id || '||R' AS splink_row_id, c.candidate_pair_id, p.* FROM candidate_core c INNER JOIN scoring_personas p ON c.persona_id_high = CAST(p.persona_idno AS VARCHAR)")
            counts = connection.execute("SELECT (SELECT COUNT(*) FROM candidate_core) AS pairs, (SELECT COUNT(*) FROM candidate_left) AS left_rows, (SELECT COUNT(*) FROM candidate_right) AS right_rows").fetchdf()
            require((counts.iloc[0] == len(pairs)).all(), "A scoring join lost an expanded candidate persona.")

            scoring_settings = copy.deepcopy(trained_settings)
            scoring_settings["link_type"] = "link_only"
            scoring_settings["unique_id_column_name"] = "splink_row_id"
            scoring_settings["blocking_rules_to_generate_predictions"] = ["l.candidate_pair_id = r.candidate_pair_id"]
            scoring_settings["additional_columns_to_retain"] = ["candidate_pair_id", "persona_idno", "event_key", "event_type", "role_standard"]
            scoring_settings["retain_matching_columns"] = True
            scoring_settings["retain_intermediate_calculation_columns"] = False

            linker = Linker(
                ["candidate_left", "candidate_right"], scoring_settings,
                db_api=DuckDBAPI(connection=connection),
                input_table_aliases=["candidate_left", "candidate_right"],
            )
            predictions = linker.inference.predict().as_pandas_dataframe()
        finally:
            connection.close()

    require(len(predictions) == len(pairs), "Prediction count differs from expanded candidate count.")
    predictions["pair_key"] = predictions.apply(
        lambda row: "||".join(sorted([str(row["persona_idno_l"]), str(row["persona_idno_r"])])), axis=1
    )
    scored = evidence.merge(
        predictions[["pair_key", "match_probability", "match_weight"]],
        on="pair_key", how="inner", validate="1:1",
    ).copy()
    require(len(scored) == len(evidence), "Prediction merge changed the expanded candidate count.")
    require(scored["match_probability"].notna().all(), "A scored expanded candidate has no probability.")

    high_priority = (
        scored["match_probability"].ge(0.90)
        & scored["review_support_score"].ge(5)
    )
    scored["expanded_scoring_disposition"] = "manual_review"
    scored.loc[high_priority, "expanded_scoring_disposition"] = "high_priority_review"
    scored["automatic_identity_cluster_change"] = False
    scored["decision_basis"] = "locked_v3_model_plus_expanded_candidate_evidence; review_only"
    scored = scored.sort_values(["expanded_scoring_disposition", "match_probability", "review_support_score"], ascending=[True, False, False]).reset_index(drop=True)

    scored.to_parquet(SCORED_PATH, index=False)
    scored.loc[scored["expanded_scoring_disposition"].eq("high_priority_review")].to_csv(HIGH_PRIORITY_PATH, index=False)
    scored.loc[scored["expanded_scoring_disposition"].eq("manual_review")].to_csv(MANUAL_REVIEW_PATH, index=False)

    summary = pd.DataFrame([
        {"metric": "expanded_candidates_scored", "value": len(scored)},
        {"metric": "high_priority_review_pairs", "value": int(high_priority.sum())},
        {"metric": "manual_review_pairs", "value": int((~high_priority).sum())},
        {"metric": "minimum_match_probability", "value": float(scored["match_probability"].min())},
        {"metric": "median_match_probability", "value": float(scored["match_probability"].median())},
        {"metric": "maximum_match_probability", "value": float(scored["match_probability"].max())},
        {"metric": "gender_conflicts", "value": int(scored["gender_evidence_conflict"].sum())},
        {"metric": "chronology_flags", "value": int(scored["chronology_review_flag"].sum())},
        {"metric": "same_event_same_role_flags", "value": int(scored["same_event_same_role"].sum())},
        {"metric": "automatic_identity_cluster_changes", "value": 0},
    ])
    summary.to_csv(SUMMARY_PATH, index=False)
    print(summary.to_string(index=False))
    print(f"Saved review-only scores: {SCORED_PATH}")
    print(f"Saved high-priority review queue: {HIGH_PRIORITY_PATH}")
    print(f"Saved manual review queue: {MANUAL_REVIEW_PATH}")


if __name__ == "__main__":
    main()
