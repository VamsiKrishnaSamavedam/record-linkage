"""Create a compact, reproducible validation sample for expanded PRL candidates."""

from pathlib import Path
import hashlib

import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SCORED_PATH = PROJECT_ROOT / "data" / "processed" / "splink_hybrid_v3_expanded_candidate_scores_v1.parquet"
REVIEW_DIR = PROJECT_ROOT / "outputs" / "review"
REPORT_DIR = PROJECT_ROOT / "outputs" / "reports"
SAMPLE_PATH = REVIEW_DIR / "splink_hybrid_v3_expanded_candidate_validation_sample_v1.csv"
SUMMARY_PATH = REPORT_DIR / "splink_hybrid_v3_expanded_candidate_validation_sample_summary_v1.csv"

TARGETS = [
    ("godparent_high_priority", 60, True, "high_priority_review"),
    ("non_godparent_high_priority", 20, False, "high_priority_review"),
    ("godparent_manual_review", 25, True, "manual_review"),
    ("non_godparent_manual_review", 15, False, "manual_review"),
]


def pick_diverse(frame: pd.DataFrame, target: int, selected_ids: set[str]) -> pd.DataFrame:
    """Choose deterministic rows while reducing repeated-person dominance."""
    ordered = frame.assign(
        _stable_order=frame["pair_key"].map(
            lambda value: int(hashlib.sha256(str(value).encode("utf-8")).hexdigest()[:16], 16)
        )
    ).sort_values(
        ["review_support_score", "match_probability", "_stable_order"], ascending=[False, False, True]
    )
    chosen = []
    for row in ordered.itertuples(index=False):
        left, right = str(row.persona_id_l), str(row.persona_id_r)
        if left not in selected_ids and right not in selected_ids:
            chosen.append(row._asdict())
            selected_ids.update([left, right])
        if len(chosen) == target:
            break
    if len(chosen) < target:
        chosen_keys = {row["pair_key"] for row in chosen}
        for row in ordered.itertuples(index=False):
            if row.pair_key not in chosen_keys:
                chosen.append(row._asdict())
                chosen_keys.add(row.pair_key)
            if len(chosen) == target:
                break
    return pd.DataFrame(chosen).drop(columns=["_stable_order"], errors="ignore")


def main() -> None:
    if not SCORED_PATH.exists():
        raise FileNotFoundError(f"Score expanded candidates first: {SCORED_PATH}")
    REVIEW_DIR.mkdir(parents=True, exist_ok=True)
    REPORT_DIR.mkdir(parents=True, exist_ok=True)

    scores = pd.read_parquet(SCORED_PATH).copy()
    scores["godparent_rule"] = scores["blocking_rules"].fillna("").str.contains(
        "marriage_godparent_canonical_full_name_plus_place", regex=False
    )
    selected_ids: set[str] = set()
    samples = []
    summary_rows = []

    for group_name, target, godparent_rule, disposition in TARGETS:
        pool = scores.loc[
            scores["godparent_rule"].eq(godparent_rule)
            & scores["expanded_scoring_disposition"].eq(disposition)
        ].copy()
        picked = pick_diverse(pool, target, selected_ids)
        picked["selection_group"] = group_name
        picked["selection_reason"] = "stratified_candidate_validation; no automatic identity change"
        samples.append(picked)
        summary_rows.append({
            "selection_group": group_name,
            "available_pairs": len(pool),
            "target_sample_size": target,
            "selected_pairs": len(picked),
        })

    sample = pd.concat(samples, ignore_index=True, sort=False)
    if sample["pair_key"].duplicated().any():
        raise AssertionError("Validation sample contains duplicate pair keys.")
    sample["reviewer_decision"] = ""
    sample["reviewer_notes"] = ""
    sample["reviewed_by"] = ""
    sample["reviewed_at"] = ""
    columns_first = [
        "selection_group", "selection_reason", "pair_key", "persona_id_l", "persona_id_r",
        "full_name_clean_l", "full_name_clean_r", "event_type_l", "event_type_r",
        "event_year_l", "event_year_r", "role_standard_l", "role_standard_r",
        "event_place_linkage_key_l", "event_place_linkage_key_r", "parent_pair_clean_l",
        "parent_pair_clean_r", "spouse_name_clean_ctx_l", "spouse_name_clean_ctx_r",
        "match_probability", "match_weight", "review_support_score", "blocking_rules",
        "expanded_scoring_disposition", "reviewer_decision", "reviewer_notes", "reviewed_by", "reviewed_at",
    ]
    sample = sample[[column for column in columns_first if column in sample.columns]]
    sample.to_csv(SAMPLE_PATH, index=False)

    summary = pd.DataFrame(summary_rows)
    summary = pd.concat([summary, pd.DataFrame([{
        "selection_group": "total",
        "available_pairs": len(scores),
        "target_sample_size": sum(item[1] for item in TARGETS),
        "selected_pairs": len(sample),
    }])], ignore_index=True)
    summary.to_csv(SUMMARY_PATH, index=False)
    print(summary.to_string(index=False))
    print(f"Saved validation sample: {SAMPLE_PATH}")


if __name__ == "__main__":
    main()
