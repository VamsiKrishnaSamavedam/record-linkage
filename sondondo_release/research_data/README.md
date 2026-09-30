# Sondondo Research-Team Data Package

This folder is a curated internal data package for the Sondondo research team. It is built from the current validated local outputs by running:

```text
python scripts/build_research_team_data_package.py
```

`MANIFEST.csv` explains every included file, its source path, its role, and whether it is safe-release material or input/review material.

## Package sections

| Prefix | Contents | How to interpret it |
| --- | --- | --- |
| `01_` | Original event and persona tables | Source data; do not overwrite. |
| `02_` | Reviewed name, gender, and label materials | Expert-informed matching inputs. |
| `03_` | Current identity and family membership tables | Current safe identity/family results. |
| `04_` | Safe graph people, relationships, and provenance | Use for family-graph research and visualization. |
| `05_` | Secure multi-record identity evidence | Use for restricted downstream linkage research. |
| `06_` | Expanded candidate review queues | Review-only. These rows are not accepted matches. |
| `07_` | Sibling and spouse/baptism candidate queues | Review-only. These rows are not family-graph edges. |
| `08_` | Validation and release summary files | Read these before interpreting the other files. |

## Important boundaries

The trusted family relationship file contains only validated edges. The review queues are intentionally separate and must not be treated as confirmed identities or family connections. Original source transcription remains available in the `01_` files.

This folder is designed for the approved Sondondo research team. Confirm the intended repository visibility and data-sharing permissions with the project leads before making it publicly accessible.
