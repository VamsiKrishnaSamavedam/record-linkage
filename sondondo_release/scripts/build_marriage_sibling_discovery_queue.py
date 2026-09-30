"""Build professor-proposed sibling candidates as a review-only PRL enhancement.

For each marriage spouse with a valid recorded birth date and parent pair, find
baptismal children of the same named parents whose recorded/observed birth year
is within ±15 years.  The rule intentionally permits births before a marriage.
It creates no identity or family-cluster changes.
"""

from __future__ import annotations

import re
import unicodedata
from pathlib import Path

import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parents[1]
RAW_DIR = PROJECT_ROOT / "data" / "raw"
REVIEW_DIR = PROJECT_ROOT / "outputs" / "review"
REPORT_DIR = PROJECT_ROOT / "outputs" / "reports"

MARRIAGES_PATH = RAW_DIR / "matrimonios_clean.csv"
BAPTISMS_PATH = RAW_DIR / "bautismos_clean.csv"
QUEUE_PATH = REVIEW_DIR / "marriage_parent_pair_sibling_discovery_queue_v1.csv"
SUMMARY_PATH = REPORT_DIR / "marriage_parent_pair_sibling_discovery_summary_v1.csv"

WINDOW_YEARS = 15
MIN_PLAUSIBLE_MARRIAGE_AGE = 12
MAX_PLAUSIBLE_MARRIAGE_AGE = 80


def linkage_key(value: object) -> str:
    if pd.isna(value):
        return ""
    text = unicodedata.normalize("NFD", str(value).strip().lower())
    text = "".join(character for character in text if unicodedata.category(character) != "Mn")
    text = re.sub(r"[^a-z\s]", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def full_name_key(first: object, last: object) -> str:
    return " ".join(part for part in [linkage_key(first), linkage_key(last)] if part).strip()


def year_from_date(values: pd.Series) -> pd.Series:
    return pd.to_numeric(
        values.astype("string").str.extract(r"\b((?:17|18|19)\d{2})\b", expand=False),
        errors="coerce",
    ).astype("Int64")


def nonempty_pair(frame: pd.DataFrame, first_col: str, last_col: str) -> pd.Series:
    return frame[first_col].map(linkage_key).ne("") & frame[last_col].map(linkage_key).ne("")


def main() -> None:
    for path in [MARRIAGES_PATH, BAPTISMS_PATH]:
        if not path.exists():
            raise FileNotFoundError(f"Missing required raw data: {path}")
    REVIEW_DIR.mkdir(parents=True, exist_ok=True)
    REPORT_DIR.mkdir(parents=True, exist_ok=True)

    marriages = pd.read_csv(MARRIAGES_PATH, dtype=str).fillna("")
    baptisms = pd.read_csv(BAPTISMS_PATH, dtype=str).fillna("")
    marriages["marriage_year"] = year_from_date(marriages["event_date"])

    spouse_frames = []
    for spouse_role in ["husband", "wife"]:
        spouse = pd.DataFrame({
            "marriage_identifier": marriages["identifier"],
            "marriage_event_date": marriages["event_date"],
            "marriage_year": marriages["marriage_year"],
            "marriage_place_raw": marriages["event_place"],
            "spouse_role": spouse_role,
            "spouse_gender": "male" if spouse_role == "husband" else "female",
            "spouse_name_raw": marriages[f"{spouse_role}_name"],
            "spouse_lastname_raw": marriages[f"{spouse_role}_lastname"],
            "spouse_birth_date": marriages[f"{spouse_role}_birth_date"],
            "father_name_raw": marriages[f"{spouse_role}_father_name"],
            "father_lastname_raw": marriages[f"{spouse_role}_father_lastname"],
            "mother_name_raw": marriages[f"{spouse_role}_mother_name"],
            "mother_lastname_raw": marriages[f"{spouse_role}_mother_lastname"],
        })
        spouse_frames.append(spouse)
    spouses = pd.concat(spouse_frames, ignore_index=True)
    spouses["spouse_full_name_key"] = [
        full_name_key(first, last) for first, last in zip(spouses["spouse_name_raw"], spouses["spouse_lastname_raw"])
    ]
    spouses["father_full_name_key"] = [
        full_name_key(first, last) for first, last in zip(spouses["father_name_raw"], spouses["father_lastname_raw"])
    ]
    spouses["mother_full_name_key"] = [
        full_name_key(first, last) for first, last in zip(spouses["mother_name_raw"], spouses["mother_lastname_raw"])
    ]
    spouses["parent_pair_key"] = spouses["father_full_name_key"] + " | " + spouses["mother_full_name_key"]
    spouses["spouse_birth_year"] = year_from_date(spouses["spouse_birth_date"])
    spouses["marriage_age_years"] = spouses["marriage_year"] - spouses["spouse_birth_year"]
    spouse_eligible = (
        spouses["spouse_birth_year"].notna()
        & spouses["marriage_year"].notna()
        & spouses["father_full_name_key"].ne("")
        & spouses["mother_full_name_key"].ne("")
        & spouses["marriage_age_years"].between(MIN_PLAUSIBLE_MARRIAGE_AGE, MAX_PLAUSIBLE_MARRIAGE_AGE)
    )
    spouses = spouses.loc[spouse_eligible].copy()

    children = pd.DataFrame({
        "baptism_identifier": baptisms["identifier"],
        "baptism_event_date": baptisms["event_date"],
        "baptism_place_raw": baptisms["event_place"],
        "child_name_raw": baptisms["baptized_name"],
        "child_lastname_raw": baptisms["baptized_lastname"],
        "child_birth_date": baptisms["baptized_birth_date"],
        "father_name_raw": baptisms["father_name"],
        "father_lastname_raw": baptisms["father_lastname"],
        "mother_name_raw": baptisms["mother_name"],
        "mother_lastname_raw": baptisms["mother_lastname"],
    })
    children["child_full_name_key"] = [
        full_name_key(first, last) for first, last in zip(children["child_name_raw"], children["child_lastname_raw"])
    ]
    children["father_full_name_key"] = [
        full_name_key(first, last) for first, last in zip(children["father_name_raw"], children["father_lastname_raw"])
    ]
    children["mother_full_name_key"] = [
        full_name_key(first, last) for first, last in zip(children["mother_name_raw"], children["mother_lastname_raw"])
    ]
    children["parent_pair_key"] = children["father_full_name_key"] + " | " + children["mother_full_name_key"]
    children["child_birth_year"] = year_from_date(children["child_birth_date"])
    children["baptism_year"] = year_from_date(children["baptism_event_date"])
    children["child_timing_year"] = children["child_birth_year"].fillna(children["baptism_year"])
    children["child_timing_source"] = "baptism_event_year_fallback"
    children.loc[children["child_birth_year"].notna(), "child_timing_source"] = "recorded_birth_year"
    child_eligible = (
        children["child_timing_year"].notna()
        & children["father_full_name_key"].ne("")
        & children["mother_full_name_key"].ne("")
    )
    children = children.loc[child_eligible].copy()

    candidates = spouses.merge(children, on="parent_pair_key", how="inner", suffixes=("_marriage", "_baptism"))
    candidates["father_full_name_key"] = candidates["father_full_name_key_marriage"]
    candidates["mother_full_name_key"] = candidates["mother_full_name_key_marriage"]
    candidates["birth_year_gap"] = (candidates["spouse_birth_year"] - candidates["child_timing_year"]).abs()
    candidates = candidates.loc[candidates["birth_year_gap"].le(WINDOW_YEARS)].copy()
    candidates["candidate_type"] = "potential_sibling"
    candidates.loc[
        candidates["spouse_full_name_key"].eq(candidates["child_full_name_key"])
        & candidates["spouse_full_name_key"].ne(""),
        "candidate_type",
    ] = "possible_spouse_self_baptism"
    candidates["same_normalized_place"] = candidates["marriage_place_raw"].map(linkage_key).eq(
        candidates["baptism_place_raw"].map(linkage_key)
    )
    candidates["within_birth_window"] = True
    candidates["birth_before_marriage_allowed"] = candidates["child_timing_year"].lt(candidates["marriage_year"])
    candidates["automatic_identity_cluster_change"] = False
    candidates["review_decision"] = "needs_review"
    candidates["review_reason"] = "same_named_parent_pair and child/spouse timing within professor-approved ±15-year window; no marriage-date exclusion applied"
    candidates = candidates.drop_duplicates(["marriage_identifier", "spouse_role", "baptism_identifier"]).copy()
    candidates = candidates.sort_values(
        ["candidate_type", "same_normalized_place", "birth_year_gap", "marriage_identifier"],
        ascending=[True, False, True, True],
    ).reset_index(drop=True)

    output_columns = [
        "candidate_type", "marriage_identifier", "marriage_event_date", "marriage_year",
        "spouse_role", "spouse_gender", "spouse_name_raw", "spouse_lastname_raw",
        "spouse_birth_date", "spouse_birth_year", "marriage_age_years",
        "baptism_identifier", "baptism_event_date", "baptism_place_raw",
        "child_name_raw", "child_lastname_raw", "child_birth_date", "child_timing_year",
        "child_timing_source", "father_full_name_key", "mother_full_name_key", "parent_pair_key",
        "birth_year_gap", "within_birth_window", "birth_before_marriage_allowed",
        "same_normalized_place", "review_decision", "review_reason", "automatic_identity_cluster_change",
    ]
    candidates[output_columns].to_csv(QUEUE_PATH, index=False)

    summary = pd.DataFrame([
        {"metric": "marriage_records", "value": len(marriages)},
        {"metric": "marriage_spouse_rows", "value": len(marriages) * 2},
        {"metric": "eligible_marriage_spouses_with_parent_pair_and_plausible_birth_timing", "value": len(spouses)},
        {"metric": "eligible_baptism_children_with_parent_pair", "value": len(children)},
        {"metric": "review_only_parent_pair_window_candidates", "value": len(candidates)},
        {"metric": "potential_siblings", "value": int(candidates["candidate_type"].eq("potential_sibling").sum())},
        {"metric": "possible_spouse_self_baptisms", "value": int(candidates["candidate_type"].eq("possible_spouse_self_baptism").sum())},
        {"metric": "children_before_marriage_kept", "value": int(candidates["birth_before_marriage_allowed"].sum())},
        {"metric": "automatic_identity_cluster_changes", "value": 0},
        {"metric": "window_years", "value": WINDOW_YEARS},
    ])
    summary.to_csv(SUMMARY_PATH, index=False)
    print(summary.to_string(index=False))
    print(f"Saved sibling-discovery review queue: {QUEUE_PATH}")


if __name__ == "__main__":
    main()
