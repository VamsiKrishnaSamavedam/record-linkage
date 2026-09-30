"""Create a restricted, review-only godparent linkage queue.

Professor guidance: broad marriage/godparent candidate matching is held.  This
stage looks only at candidate pairs where the godparent appearance belongs to
one of the securely deduplicated multi-record people and where a baptismal
year supports an age of at least 13 at the godparent event.  It never changes
an identity cluster or family cluster.
"""

from pathlib import Path

import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parents[1]
INTERIM_DIR = PROJECT_ROOT / "data" / "interim"
PROCESSED_DIR = PROJECT_ROOT / "data" / "processed"
REPORT_DIR = PROJECT_ROOT / "outputs" / "reports"
REVIEW_DIR = PROJECT_ROOT / "outputs" / "review"

CONTEXT_PATH = INTERIM_DIR / "persona_context_name_enriched_v1.parquet"
MULTI_RECORD_EVIDENCE_PATH = REPORT_DIR / "securely_deduplicated_persona_evidence_v1.csv"
EXPANDED_SCORES_PATH = PROCESSED_DIR / "splink_hybrid_v3_expanded_candidate_scores_v1.parquet"
ELIGIBLE_QUEUE_PATH = REVIEW_DIR / "unique_adult_godparent_identity_candidates_v1.csv"
HELD_QUEUE_PATH = REVIEW_DIR / "unique_adult_godparent_identity_held_age_unknown_v1.csv"
SUMMARY_PATH = REPORT_DIR / "unique_adult_godparent_identity_candidate_summary_v1.csv"

GODPARENT_RULE = "marriage_godparent_canonical_full_name_plus_place"


def require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def normalized_text(series: pd.Series) -> pd.Series:
    return series.fillna("").astype(str).str.strip().str.lower()


def main() -> None:
    for directory in [REVIEW_DIR, REPORT_DIR]:
        directory.mkdir(parents=True, exist_ok=True)
    for path in [CONTEXT_PATH, MULTI_RECORD_EVIDENCE_PATH, EXPANDED_SCORES_PATH]:
        require(path.exists(), f"Missing required input: {path}")

    context = pd.read_parquet(CONTEXT_PATH).copy()
    multi = pd.read_csv(MULTI_RECORD_EVIDENCE_PATH, dtype=str).copy()
    scores = pd.read_parquet(EXPANDED_SCORES_PATH).copy()

    context_required = {"persona_idno", "event_year", "event_type", "role_standard"}
    multi_required = {"persona_idno", "identity_person_id", "source_persona_count"}
    score_required = {
        "pair_key", "persona_id_l", "persona_id_r", "blocking_rules",
        "role_standard_l", "role_standard_r", "event_year_l", "event_year_r",
        "canonical_full_name_exact", "match_probability", "review_support_score",
    }
    require(context_required.issubset(context.columns), "Persona context is missing event or role fields.")
    require(multi_required.issubset(multi.columns), "Secure multi-record evidence is missing identity fields.")
    require(score_required.issubset(scores.columns), "Expanded scores are missing required candidate evidence.")
    require(context["persona_idno"].is_unique, "Persona context has duplicate persona IDs.")
    require(multi["persona_idno"].is_unique, "Multi-record persona evidence has duplicate persona IDs.")
    require(scores["pair_key"].is_unique, "Expanded scores has duplicate candidate pairs.")

    # The secure report is the authoritative 1,564-person population.  We only
    # retain godparent appearances that already belong to that population.
    multi["persona_idno"] = multi["persona_idno"].astype(str)
    multi["source_persona_count"] = pd.to_numeric(multi["source_persona_count"], errors="coerce")
    multi = multi.loc[multi["source_persona_count"].ge(2)].copy()
    require(multi["identity_person_id"].nunique() == 1564, "The secure multi-record population is no longer 1,564 people.")

    context["persona_idno"] = context["persona_idno"].astype(str)
    context["event_year"] = pd.to_numeric(context["event_year"], errors="coerce")
    context["event_type_key"] = normalized_text(context["event_type"])
    context["role_standard_key"] = normalized_text(context["role_standard"])
    identity_context = multi[["persona_idno", "identity_person_id", "source_persona_count"]].merge(
        context[["persona_idno", "event_year", "event_type_key", "role_standard_key"]],
        on="persona_idno", how="left", validate="1:1",
    )
    require(identity_context["event_year"].notna().any(), "Secure identity evidence has no event years.")

    # A known baptism of the person is required for an explicit age calculation.
    baptism_rows = identity_context.loc[
        identity_context["event_type_key"].str.contains("baut", na=False)
        & identity_context["role_standard_key"].isin({"baptized", "baptised", "baptism_child", "child"})
        & identity_context["event_year"].notna(),
        ["identity_person_id", "event_year"],
    ].copy()
    identity_birth = baptism_rows.groupby("identity_person_id", as_index=False).agg(
        identity_baptism_year=("event_year", "min")
    )

    scores["blocking_rules"] = scores["blocking_rules"].fillna("").astype(str)
    godparent_scores = scores.loc[scores["blocking_rules"].str.contains(GODPARENT_RULE, regex=False)].copy()
    require(len(godparent_scores) > 0, "No expanded marriage-godparent candidates were found.")

    expanded_rows = []
    for side, other in [("l", "r"), ("r", "l")]:
        role = normalized_text(godparent_scores[f"role_standard_{side}"])
        side_rows = godparent_scores.loc[role.eq("godparent")].copy()
        side_rows["godparent_persona_id"] = side_rows[f"persona_id_{side}"].astype(str)
        side_rows["candidate_persona_id"] = side_rows[f"persona_id_{other}"].astype(str)
        side_rows["godparent_event_year"] = pd.to_numeric(side_rows[f"event_year_{side}"], errors="coerce")
        side_rows["candidate_event_year"] = pd.to_numeric(side_rows[f"event_year_{other}"], errors="coerce")
        side_rows["godparent_name"] = side_rows.get(f"full_name_clean_{side}", "")
        side_rows["candidate_name"] = side_rows.get(f"full_name_clean_{other}", "")
        side_rows["godparent_event_type"] = side_rows.get(f"event_type_{side}", "")
        side_rows["candidate_event_type"] = side_rows.get(f"event_type_{other}", "")
        expanded_rows.append(side_rows)

    candidates = pd.concat(expanded_rows, ignore_index=True, sort=False)
    candidates = candidates.merge(
        multi[["persona_idno", "identity_person_id", "source_persona_count"]].rename(columns={"persona_idno": "godparent_persona_id"}),
        on="godparent_persona_id", how="inner", validate="m:1",
    )
    candidates = candidates.merge(identity_birth, on="identity_person_id", how="left", validate="m:1")
    candidates["age_at_godparent_event"] = candidates["godparent_event_year"] - candidates["identity_baptism_year"]
    candidates["age_evidence_status"] = "age_unknown_no_person_baptism_in_secure_identity"
    candidates.loc[candidates["age_at_godparent_event"].lt(13), "age_evidence_status"] = "under_13_at_godparent_event"
    candidates.loc[candidates["age_at_godparent_event"].ge(13), "age_evidence_status"] = "confirmed_13_or_older"
    candidates["canonical_full_name_exact"] = candidates["canonical_full_name_exact"].astype(bool)
    candidates["review_disposition"] = "held_age_or_identity_evidence_insufficient"
    eligible = candidates["age_evidence_status"].eq("confirmed_13_or_older") & candidates["canonical_full_name_exact"]
    candidates.loc[eligible, "review_disposition"] = "eligible_for_professor_review"
    candidates["automatic_identity_cluster_change"] = False
    candidates["decision_basis"] = (
        "secure_multi_record_identity_plus_confirmed_age_13_or_older_plus_canonical_name; review_only"
    )

    ordered_columns = [
        "pair_key", "identity_person_id", "source_persona_count", "godparent_persona_id", "candidate_persona_id",
        "godparent_name", "candidate_name", "godparent_event_type", "candidate_event_type",
        "godparent_event_year", "candidate_event_year", "identity_baptism_year", "age_at_godparent_event",
        "age_evidence_status", "canonical_full_name_exact", "match_probability", "review_support_score",
        "event_place_linkage_key_l", "event_place_linkage_key_r", "parent_pair_clean_l", "parent_pair_clean_r",
        "spouse_name_clean_ctx_l", "spouse_name_clean_ctx_r", "blocking_rules", "review_disposition",
        "decision_basis", "automatic_identity_cluster_change",
    ]
    candidates = candidates[[column for column in ordered_columns if column in candidates.columns]].drop_duplicates("pair_key")
    eligible_queue = candidates.loc[candidates["review_disposition"].eq("eligible_for_professor_review")].copy()
    held_queue = candidates.loc[~candidates["review_disposition"].eq("eligible_for_professor_review")].copy()
    eligible_queue = eligible_queue.sort_values(["match_probability", "review_support_score"], ascending=[False, False])
    held_queue = held_queue.sort_values(["age_evidence_status", "match_probability"], ascending=[True, False])

    eligible_queue.to_csv(ELIGIBLE_QUEUE_PATH, index=False)
    held_queue.to_csv(HELD_QUEUE_PATH, index=False)
    summary = pd.DataFrame([
        {"metric": "broad_godparent_candidates_held_outside_this_stage", "value": int(len(godparent_scores))},
        {"metric": "secure_multi_record_people_available", "value": int(multi["identity_person_id"].nunique())},
        {"metric": "godparent_candidates_with_secure_identity", "value": int(len(candidates))},
        {"metric": "eligible_confirmed_adult_review_candidates", "value": int(len(eligible_queue))},
        {"metric": "held_age_unknown_or_under_13_candidates", "value": int(len(held_queue))},
        {"metric": "automatic_identity_cluster_changes", "value": 0},
    ])
    summary.to_csv(SUMMARY_PATH, index=False)

    require(not eligible_queue["automatic_identity_cluster_change"].any(), "This stage must never merge identities.")
    print(summary.to_string(index=False))
    print(f"Eligible review queue: {ELIGIBLE_QUEUE_PATH}")
    print(f"Held queue: {HELD_QUEUE_PATH}")


if __name__ == "__main__":
    main()
