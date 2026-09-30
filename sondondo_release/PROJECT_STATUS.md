# Sondondo PRL Project Status

**Last documented:** September 2026

## Purpose

The project reconstructs historical people and trusted family relationships from Sondondo baptism, marriage, and burial records. It preserves source transcription, records expert review separately, and prevents unreviewed candidates from entering the safe family release.

## Maintained workflow

Run the three consolidated notebooks in order:

1. `notebooks/01_name_reference_and_persona_enrichment.ipynb`
2. `notebooks/02_name_candidates_evidence_and_safeguards.ipynb`
3. `notebooks/03_name_review_and_model_evaluation.ipynb`

Older work is retained in `notebooks/archive/` only for provenance. It is not the default workflow. See `README.md` for the current three-notebook workflow.

## Current safe family release

| Metric | Current value |
| --- | ---: |
| Input personas | 47,072 |
| Personas represented through safe identity linkage | 41,251 |
| Provisional singleton personas | 5,821 |
| Identity-level people | 44,995 |
| Family clusters | 29,013 |
| Trusted family relationships | 16,281 |
| Trusted cross-cluster relationship failures | 0 |
| Release ready for safe family lookup | Yes |

The evidence source for these figures is `outputs/reports/family_cluster_release_readiness_v3.csv`.

## Held for review

The following sets are intentionally excluded from automatic identity or family changes:

- 8,093 expanded candidate links;
- 480 sibling-discovery candidates generated using shared parents and the ±15-year rule;
- broad godparent candidates, which require additional identity and adult-age evidence;
- 5,821 provisional singleton personas.

Holding these cases is a safety feature, not a failure. Future work should validate representative samples, document an approved rule, then rerun and compare the validation outputs.

## Main local deliverables

- Safe graph import package: `outputs/graph_imports/safe_family_release_v3/`
- Readable family diagrams: `outputs/yed/`
- Family-release readiness report: `outputs/reports/family_cluster_release_readiness_v3.csv`
- Sibling review package: `outputs/review/professor_potential_siblings_with_parents_v1.csv`
- Current source-persona/family membership: `data/processed/identity_aware_family_cluster_membership_final_v3.parquet`

## GitHub release position

The repository is prepared to publish code, documentation, and the curated internal `research_data/` package. Other local source copies, generated person-level outputs, archive material, and heavy visual exports should be excluded from GitHub unless the research team explicitly approves them.
