"""Create one yEd file containing three selected, trusted demonstration families."""

from __future__ import annotations

from collections import defaultdict
from pathlib import Path
from xml.sax.saxutils import escape

import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parents[1]
INPUT_DIR = PROJECT_ROOT / "outputs" / "graph_imports" / "safe_family_release_v3"
OUTPUT_PATH = PROJECT_ROOT / "outputs" / "yed" / "selected_demo_families.graphml"

SELECTED = {
    "HP-00012714": "FCL2-018445",  # Damian Chinchay
    "HP-00019073": "FCL2-016726",  # Eusebio Llamocca
    "HP-00023048": "FCL2-017805",  # Corpus Quispe
}


def node_xml(person_id: str, label: str, gender: str, x: int, y: int) -> str:
    color = {"male": "#CFE8FF", "female": "#F8D6E8"}.get(gender, "#E7E7E7")
    return f"""    <node id="{escape(person_id)}">
      <data key="d0">
        <y:ShapeNode>
          <y:Geometry height="68.0" width="210.0" x="{x}.0" y="{y}.0"/>
          <y:Fill color="{color}" transparent="false"/>
          <y:BorderStyle color="#4D4D4D" type="line" width="1.5"/>
          <y:NodeLabel alignment="center" autoSizePolicy="content" fontFamily="Arial" fontSize="12" hasLineColor="false" modelName="custom" textAlignment="center">{escape(label)}</y:NodeLabel>
          <y:Shape type="roundrectangle"/>
        </y:ShapeNode>
      </data>
    </node>"""


def edge_xml(edge_id: str, source: str, target: str, relationship: str) -> str:
    spouse = relationship == "SPOUSE_OF"
    color = "#777777" if spouse else "#345D7E"
    target_arrow = "none" if spouse else "standard"
    label = "spouses" if spouse else relationship.replace("_OF", "").lower().replace("_", " ")
    return f"""    <edge id="{edge_id}" source="{escape(source)}" target="{escape(target)}">
      <data key="d1">
        <y:PolyLineEdge>
          <y:LineStyle color="{color}" type="line" width="1.5"/>
          <y:Arrows source="none" target="{target_arrow}"/>
          <y:EdgeLabel alignment="center" backgroundColor="#FFFFFF" fontFamily="Arial" fontSize="10" hasLineColor="false">{label}</y:EdgeLabel>
        </y:PolyLineEdge>
      </data>
    </edge>"""


def assign_positions(people: pd.DataFrame, relationships: pd.DataFrame, cluster_index: int) -> dict[str, tuple[int, int]]:
    person_id_col = "person_id:ID(Person)"
    parents = relationships[relationships[":TYPE"].isin(["FATHER_OF", "MOTHER_OF"])].copy()
    children_by_parent: dict[str, list[str]] = defaultdict(list)
    parents_by_child: dict[str, list[str]] = defaultdict(list)
    for _, row in parents.iterrows():
        children_by_parent[row[":START_ID(Person)"]].append(row[":END_ID(Person)"])
        parents_by_child[row[":END_ID(Person)"]].append(row[":START_ID(Person)"])

    level: dict[str, int] = {person_id: 0 for person_id in people[person_id_col] if person_id not in parents_by_child}
    pending = set(people[person_id_col]) - set(level)
    while pending:
        progressed = False
        for person_id in list(pending):
            known_parents = parents_by_child.get(person_id, [])
            if known_parents and all(parent in level for parent in known_parents):
                level[person_id] = max(level[parent] for parent in known_parents) + 1
                pending.remove(person_id)
                progressed = True
        if not progressed:
            for person_id in pending:
                level[person_id] = 0
            break

    people = people.assign(level=people[person_id_col].map(level)).sort_values(["level", "preferred_name"])
    positions: dict[str, tuple[int, int]] = {}
    base_x = cluster_index * 1100
    for row_index, (_, person) in enumerate(people.groupby("level", sort=True)):
        for column_index, (_, person_row) in enumerate(person.iterrows()):
            positions[person_row[person_id_col]] = (base_x + column_index * 250, row_index * 175)
    return positions


def main() -> None:
    people = pd.read_csv(INPUT_DIR / "neo4j_people_nodes.csv")
    relationships = pd.read_csv(INPUT_DIR / "neo4j_trusted_relationships.csv")
    person_id_col = "person_id:ID(Person)"

    node_parts: list[str] = []
    edge_parts: list[str] = []
    total_people = 0
    total_relationships = 0

    for cluster_index, (focus_id, cluster_id) in enumerate(SELECTED.items()):
        cluster_people = people[people["family_cluster_id"].eq(cluster_id)].copy()
        person_ids = set(cluster_people[person_id_col])
        cluster_relationships = relationships[
            relationships[":START_ID(Person)"].isin(person_ids)
            & relationships[":END_ID(Person)"].isin(person_ids)
        ].copy()

        assert focus_id in person_ids, f"{focus_id} is not in {cluster_id}."
        assert len(cluster_people) == 8, f"{cluster_id} should contain eight people."
        assert len(cluster_relationships) == 9, f"{cluster_id} should contain nine trusted relationships."

        positions = assign_positions(cluster_people, cluster_relationships, cluster_index)
        for _, person in cluster_people.sort_values(person_id_col).iterrows():
            person_id = person[person_id_col]
            first_year = int(person["earliest_year:INT"])
            last_year = int(person["latest_year:INT"])
            appearances = int(person["source_persona_count:INT"])
            label = (
                f"{person['preferred_name'].title()}\n{person_id}\n"
                f"Gender: {str(person['gender']).strip().lower() or 'unknown'}\n"
                f"Observed: {first_year}–{last_year} | appearances: {appearances}\n"
                f"{cluster_id}"
            )
            x, y = positions[person_id]
            node_parts.append(node_xml(person_id, label, str(person["gender"]).lower(), x, y))

        for relationship_index, (_, relationship) in enumerate(cluster_relationships.reset_index(drop=True).iterrows()):
            edge_parts.append(
                edge_xml(
                    f"{cluster_index}_e{relationship_index}",
                    relationship[":START_ID(Person)"],
                    relationship[":END_ID(Person)"],
                    relationship[":TYPE"],
                )
            )

        total_people += len(cluster_people)
        total_relationships += len(cluster_relationships)

    graphml = f"""<?xml version="1.0" encoding="UTF-8" standalone="no"?>
<graphml xmlns="http://graphml.graphdrawing.org/xmlns"
    xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"
    xmlns:y="http://www.yworks.com/xml/graphml"
    xsi:schemaLocation="http://graphml.graphdrawing.org/xmlns http://www.yworks.com/xml/schema/graphml/1.1/ygraphml.xsd">
  <key for="node" id="d0" yfiles.type="nodegraphics"/>
  <key for="edge" id="d1" yfiles.type="edgegraphics"/>
  <graph edgedefault="directed" id="selected_safe_family_demonstrations">
{chr(10).join(node_parts)}
{chr(10).join(edge_parts)}
  </graph>
</graphml>
"""

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_PATH.write_text(graphml, encoding="utf-8")
    print(f"Created: {OUTPUT_PATH}")
    print(f"Family clusters: {len(SELECTED)}")
    print(f"People: {total_people}")
    print(f"Trusted relationships: {total_relationships}")


if __name__ == "__main__":
    main()
