"""Create a yEd GraphML file containing every trusted family connection."""

from __future__ import annotations

from pathlib import Path
from xml.sax.saxutils import escape

import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parents[1]
INPUT_DIR = PROJECT_ROOT / "outputs" / "graph_imports" / "safe_family_release_v3"
OUTPUT_PATH = PROJECT_ROOT / "outputs" / "yed" / "safe_family_connections_all.graphml"


def node_xml(person_id: str, label: str, gender: str) -> str:
    color = {"male": "#CFE8FF", "female": "#F8D6E8"}.get(gender, "#E7E7E7")
    return f"""    <node id="{escape(person_id)}">
      <data key="d0">
        <y:ShapeNode>
          <y:Geometry height="42.0" width="150.0" x="0.0" y="0.0"/>
          <y:Fill color="{color}" transparent="false"/>
          <y:BorderStyle color="#6B6B6B" type="line" width="1.0"/>
          <y:NodeLabel alignment="center" autoSizePolicy="content" fontFamily="Arial" fontSize="11" hasLineColor="false" modelName="custom" textAlignment="center">{escape(label)}</y:NodeLabel>
          <y:Shape type="roundrectangle"/>
        </y:ShapeNode>
      </data>
    </node>"""


def edge_xml(edge_id: str, source: str, target: str, relationship: str) -> str:
    spouse = relationship == "SPOUSE_OF"
    color = "#888888" if spouse else "#345D7E"
    arrow = "none" if spouse else "standard"
    return f"""    <edge id="{edge_id}" source="{escape(source)}" target="{escape(target)}">
      <data key="d1">
        <y:PolyLineEdge>
          <y:LineStyle color="{color}" type="line" width="1.0"/>
          <y:Arrows source="none" target="{arrow}"/>
        </y:PolyLineEdge>
      </data>
    </edge>"""


def main() -> None:
    people = pd.read_csv(INPUT_DIR / "neo4j_people_nodes.csv")
    relationships = pd.read_csv(INPUT_DIR / "neo4j_trusted_relationships.csv")

    person_id_col = "person_id:ID(Person)"
    connected_ids = set(relationships[":START_ID(Person)"]) | set(relationships[":END_ID(Person)"])
    connected_people = people[people[person_id_col].isin(connected_ids)].copy()

    assert len(relationships) == 16_281, "Trusted relationship count changed unexpectedly."
    assert len(connected_people) == 23_138, "Connected-person count changed unexpectedly."
    assert not relationships[":START_ID(Person)"].isin(connected_ids).eq(False).any()
    assert not relationships[":END_ID(Person)"].isin(connected_ids).eq(False).any()

    node_parts: list[str] = []
    for _, person in connected_people.sort_values(person_id_col).iterrows():
        gender = str(person["gender"]).strip().lower() or "unknown"
        label = f"{person['preferred_name'].title()}\n{person[person_id_col]}\nGender: {gender}"
        node_parts.append(node_xml(person[person_id_col], label, str(person["gender"]).lower()))

    edge_parts = [
        edge_xml(
            f"e{index}",
            relationship[":START_ID(Person)"],
            relationship[":END_ID(Person)"],
            relationship[":TYPE"],
        )
        for index, relationship in relationships.reset_index(drop=True).iterrows()
    ]

    graphml = f"""<?xml version="1.0" encoding="UTF-8" standalone="no"?>
<graphml xmlns="http://graphml.graphdrawing.org/xmlns"
    xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"
    xmlns:y="http://www.yworks.com/xml/graphml"
    xsi:schemaLocation="http://graphml.graphdrawing.org/xmlns http://www.yworks.com/xml/schema/graphml/1.1/ygraphml.xsd">
  <key for="node" id="d0" yfiles.type="nodegraphics"/>
  <key for="edge" id="d1" yfiles.type="edgegraphics"/>
  <graph edgedefault="directed" id="all_safe_family_connections">
{chr(10).join(node_parts)}
{chr(10).join(edge_parts)}
  </graph>
</graphml>
"""

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_PATH.write_text(graphml, encoding="utf-8")
    print(f"Created: {OUTPUT_PATH}")
    print(f"Connected people: {len(connected_people)}")
    print(f"Trusted relationships: {len(relationships)}")
    print("Excluded unconnected identity people: 21857")


if __name__ == "__main__":
    main()
