"""Create a styled yEd GraphML demonstration tree from trusted release data."""

from __future__ import annotations

from pathlib import Path
from xml.sax.saxutils import escape

import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parents[1]
INPUT_DIR = PROJECT_ROOT / "outputs" / "graph_imports" / "safe_family_release_v3"
OUTPUT_DIR = PROJECT_ROOT / "outputs" / "yed"

# Selected because it is a clear, safe, three-generation family example.
FAMILY_CLUSTER_ID = "FCL2-018445"
OUTPUT_PATH = OUTPUT_DIR / "FCL2-018445_damian_chinchay_lorenza_vivanco.graphml"


def display_year(value: object) -> str:
    if pd.isna(value):
        return "year unknown"
    return str(int(value))


def xml_node(node_id: str, label: str, gender: str, x: int, y: int) -> str:
    color = {"male": "#CFE8FF", "female": "#F8D6E8"}.get(gender, "#E7E7E7")
    return f"""    <node id="{escape(node_id)}">
      <data key="d0">
        <y:ShapeNode>
          <y:Geometry height="72.0" width="210.0" x="{x}.0" y="{y}.0"/>
          <y:Fill color="{color}" transparent="false"/>
          <y:BorderStyle color="#4D4D4D" type="line" width="1.5"/>
          <y:NodeLabel alignment="center" autoSizePolicy="content" fontFamily="Arial" fontSize="13" fontStyle="bold" hasLineColor="false" modelName="custom" textAlignment="center" verticalTextPosition="bottom">{escape(label)}</y:NodeLabel>
          <y:Shape type="roundrectangle"/>
        </y:ShapeNode>
      </data>
    </node>"""


def xml_edge(edge_id: str, source: str, target: str, relationship: str) -> str:
    spouse = relationship == "SPOUSE_OF"
    color = "#7A7A7A" if spouse else "#345D7E"
    arrow = "none" if spouse else "standard"
    label = "spouses" if spouse else relationship.replace("_OF", "").lower().replace("_", " ")
    return f"""    <edge id="{edge_id}" source="{escape(source)}" target="{escape(target)}">
      <data key="d1">
        <y:PolyLineEdge>
          <y:LineStyle color="{color}" type="line" width="1.5"/>
          <y:Arrows source="none" target="{arrow}"/>
          <y:EdgeLabel alignment="center" backgroundColor="#FFFFFF" fontFamily="Arial" fontSize="10" hasLineColor="false" textColor="#404040" visible="true">{label}</y:EdgeLabel>
        </y:PolyLineEdge>
      </data>
    </edge>"""


def main() -> None:
    people = pd.read_csv(INPUT_DIR / "neo4j_people_nodes.csv")
    relationships = pd.read_csv(INPUT_DIR / "neo4j_trusted_relationships.csv")

    people = people[people["family_cluster_id"].eq(FAMILY_CLUSTER_ID)].copy()
    assert len(people) == 8, "The selected demonstration cluster changed unexpectedly."

    person_id_col = "person_id:ID(Person)"
    person_ids = set(people[person_id_col])
    relationships = relationships[
        relationships[":START_ID(Person)"].isin(person_ids)
        & relationships[":END_ID(Person)"].isin(person_ids)
    ].copy()
    assert len(relationships) == 9, "Trusted relationship count changed unexpectedly."
    assert set(relationships[":TYPE"]) == {"FATHER_OF", "MOTHER_OF", "SPOUSE_OF"}

    # Explicit stable positions make the initial view clear. yEd can later
    # re-layout this file using Layout > Hierarchical > Top to Bottom.
    position = {
        "HP-00036913": (0, 0),      # Fernando Vivanco
        "HP-00036914": (250, 0),    # Saturna Gavilan
        "HP-00036911": (600, 0),    # Santos Chinchay
        "HP-00036912": (850, 0),    # Norberta Aivar
        "HP-00012715": (125, 175),  # Lorenza Vivanco
        "HP-00012714": (725, 175),  # Damian Chinchay
        "HP-00012713": (250, 360),  # Estefa Chinchay
        "HP-00024118": (650, 360),  # Pedro Advincula Chinchay
    }
    assert set(position) == person_ids, "Layout map does not cover every person."

    node_parts: list[str] = []
    for _, person in people.sort_values(person_id_col).iterrows():
        person_id = person[person_id_col]
        years = f"{display_year(person['earliest_year:INT'])}–{display_year(person['latest_year:INT'])}"
        source_count = int(person["source_persona_count:INT"])
        label = (
            f"{person['preferred_name'].title()}\n"
            f"{person_id}\n"
            f"Gender: {str(person['gender']).strip().lower() or 'unknown'}\n"
            f"Record years: {years} | appearances: {source_count}"
        )
        x, y = position[person_id]
        node_parts.append(xml_node(person_id, label, str(person["gender"]).lower(), x, y))

    edge_parts: list[str] = []
    for index, relationship in relationships.reset_index(drop=True).iterrows():
        edge_parts.append(
            xml_edge(
                f"e{index}",
                relationship[":START_ID(Person)"],
                relationship[":END_ID(Person)"],
                relationship[":TYPE"],
            )
        )

    graphml = f"""<?xml version="1.0" encoding="UTF-8" standalone="no"?>
<graphml xmlns="http://graphml.graphdrawing.org/xmlns"
    xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"
    xmlns:y="http://www.yworks.com/xml/graphml"
    xsi:schemaLocation="http://graphml.graphdrawing.org/xmlns http://www.yworks.com/xml/schema/graphml/1.1/ygraphml.xsd">
  <key for="node" id="d0" yfiles.type="nodegraphics"/>
  <key for="edge" id="d1" yfiles.type="edgegraphics"/>
  <graph edgedefault="directed" id="safe_family_tree">
{chr(10).join(node_parts)}
{chr(10).join(edge_parts)}
  </graph>
</graphml>
"""

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    OUTPUT_PATH.write_text(graphml, encoding="utf-8")
    print(f"Created: {OUTPUT_PATH}")
    print(f"People: {len(people)}")
    print(f"Trusted relationships: {len(relationships)}")


if __name__ == "__main__":
    main()
