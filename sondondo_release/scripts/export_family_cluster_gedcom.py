"""Export a trusted family cluster as a standards-compliant GEDCOM 5.5.1 file.

This is a presentation export only. It does not modify identity or family
linkage data. Parent-child family units are built solely from relationships
whose source is a parent and target is a child.
"""

from __future__ import annotations

import argparse
import re
from collections import defaultdict
from pathlib import Path

import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parents[1]
PROCESSED_DIR = PROJECT_ROOT / "data" / "processed"
EXPORT_DIR = PROJECT_ROOT / "outputs" / "graph_imports" / "safe_family_release_v3" / "gedcom"
PEOPLE_PATH = PROCESSED_DIR / "family_cluster_people_final_v3.parquet"
RELATIONSHIPS_PATH = PROCESSED_DIR / "family_graph_relationships_trusted.parquet"


def gedcom_text(value: object) -> str:
    text = "" if pd.isna(value) else str(value)
    return re.sub(r"[\r\n]+", " ", text).strip()


def gedcom_name(value: object) -> str:
    parts = gedcom_text(value).split()
    if not parts:
        return "Unknown /Unknown/"
    if len(parts) == 1:
        return f"{parts[0]} /{parts[0]}/"
    return f"{' '.join(parts[:-1])} /{parts[-1]}/"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("family_cluster_id", nargs="?", default="FCL2-006106")
    args = parser.parse_args()

    people = pd.read_parquet(PEOPLE_PATH)
    rels = pd.read_parquet(RELATIONSHIPS_PATH)
    cluster = people[people["family_cluster_id"].eq(args.family_cluster_id)].copy()
    if cluster.empty:
        raise ValueError(f"No people found for {args.family_cluster_id}")
    person_ids = set(cluster["identity_person_id"])
    rels = rels[
        rels["source_person_id"].isin(person_ids)
        & rels["target_person_id"].isin(person_ids)
        & rels["relationship_type"].isin(["FATHER_OF", "MOTHER_OF"])
    ].copy()

    fathers: dict[str, set[str]] = defaultdict(set)
    mothers: dict[str, set[str]] = defaultdict(set)
    for row in rels.itertuples(index=False):
        if row.relationship_type == "FATHER_OF":
            fathers[row.target_person_id].add(row.source_person_id)
        elif row.relationship_type == "MOTHER_OF":
            mothers[row.target_person_id].add(row.source_person_id)

    family_children: dict[tuple[str, str], list[str]] = defaultdict(list)
    for child in sorted(set(fathers) | set(mothers)):
        father = sorted(fathers.get(child, {""}))[0] if fathers.get(child) else ""
        mother = sorted(mothers.get(child, {""}))[0] if mothers.get(child) else ""
        family_children[(father, mother)].append(child)

    id_map = {person_id: f"I{index:04d}" for index, person_id in enumerate(sorted(person_ids), start=1)}
    family_map = {parents: f"F{index:04d}" for index, parents in enumerate(sorted(family_children), start=1)}
    child_family: dict[str, str] = {}
    spouse_families: dict[str, list[str]] = defaultdict(list)
    for parents, family_id in family_map.items():
        father, mother = parents
        for child in family_children[parents]:
            child_family[child] = family_id
        for parent in [father, mother]:
            if parent:
                spouse_families[parent].append(family_id)

    lines = [
        "0 HEAD",
        "1 SOUR Sundondo Safe Family Release v3",
        "1 GEDC",
        "2 VERS 5.5.1",
        "2 FORM LINEAGE-LINKED",
        "1 CHAR UTF-8",
    ]
    for row in cluster.sort_values("identity_person_id").itertuples(index=False):
        person_id = row.identity_person_id
        lines.extend([f"0 @{id_map[person_id]}@ INDI", f"1 NAME {gedcom_name(row.preferred_name)}"])
        gender = gedcom_text(row.gender).lower()
        if gender == "male":
            lines.append("1 SEX M")
        elif gender == "female":
            lines.append("1 SEX F")
        if pd.notna(row.earliest_year):
            lines.extend(["1 BIRT", f"2 DATE {int(row.earliest_year)}"])
        if person_id in child_family:
            lines.append(f"1 FAMC @{child_family[person_id]}@")
        for family_id in sorted(spouse_families.get(person_id, [])):
            lines.append(f"1 FAMS @{family_id}@")
        lines.append(f"1 NOTE identity_person_id: {person_id}; family_cluster_id: {args.family_cluster_id}")

    for parents, family_id in family_map.items():
        father, mother = parents
        lines.append(f"0 @{family_id}@ FAM")
        if father:
            lines.append(f"1 HUSB @{id_map[father]}@")
        if mother:
            lines.append(f"1 WIFE @{id_map[mother]}@")
        for child in sorted(family_children[parents]):
            lines.append(f"1 CHIL @{id_map[child]}@")
    lines.append("0 TRLR")

    EXPORT_DIR.mkdir(parents=True, exist_ok=True)
    output = EXPORT_DIR / f"{args.family_cluster_id}_trusted_family_tree.ged"
    output.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"People: {len(cluster)}")
    print(f"Trusted parent-child relationships: {len(rels)}")
    print(f"Family units: {len(family_map)}")
    print(f"GEDCOM: {output}")


if __name__ == "__main__":
    main()
