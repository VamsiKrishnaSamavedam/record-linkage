# Sondondo Historical Record Linkage and Family Clustering

This project reconstructs historical people and family relationships from Sondondo baptism, marriage, burial, and place records. It uses conservative probabilistic record linkage (PRL), reviewed name evidence, and family context to identify likely appearances of the same historical person while preserving the original transcription.

## Project goals

1. Preserve the original historical record transcription.
2. Identify securely deduplicated people across multiple records.
3. Build trusted family clusters from validated parent-child and spouse relationships.
4. Keep uncertain matches in separate review queues rather than merging them automatically.
5. Produce data that historians can inspect in spreadsheets, graphs, and family-tree tools.

## Current safe-release results

| Measure | Result |
| --- | ---: |
| Input personas | 47,072 |
| Personas represented through safe identity linkage | 41,251 |
| Provisional singleton personas | 5,821 |
| Identity-level people | 44,995 |
| Family clusters | 29,013 |
| Multi-person family clusters | 7,156 |
| Trusted family relationships | 16,281 |
| Trusted cross-cluster relationship failures | 0 |

These counts are documented in `research_data/08_family_cluster_release_readiness.csv`.

## Maintained notebook workflow

Run the three notebooks in this order:

1. `notebooks/01_name_reference_and_persona_enrichment.ipynb`  
   Validates reviewed name rules and name-frequency evidence, then creates canonical comparison keys, rarity evidence, and gender evidence without replacing original values.

2. `notebooks/02_name_candidates_evidence_and_safeguards.ipynb`  
   Generates conservative candidate pairs and attaches transparent name, date, role, relative, and chronology evidence. It does not automatically accept matches.

3. `notebooks/03_name_review_and_model_evaluation.ipynb`  
   Validates human-review decisions, evaluates protected name-variant evidence, and produces safe or review-only family-clustering outputs.

Each code cell contains a short markdown explanation immediately above it.

## Research data package

The `research_data/` folder is the curated internal package for the research team.

- `research_data/README.md` explains the numbered file groups.
- `research_data/MANIFEST.csv` documents every included CSV, its source, purpose, status, and file size.
- `01_` files contain original source tables.
- `02_` files contain reviewed name, gender, and decision materials.
- `03_` and `04_` files contain the safe identity and trusted family-graph release.
- `05_` files contain secure multi-record identity evidence.
- `06_` and `07_` files are review-only candidate queues. They are not confirmed matches or family relationships.
- `08_` files contain validation and release summaries.

## Reviewed rules and implementation

The rules below were built from documented historical-review guidance and are implemented as auditable code and outputs. Rules that could create a false identity or family connection are deliberately limited to candidate generation or human review.

### 1. Preserve source text; use canonical values only for comparison

The original recorded name remains in the source and persona tables. The workflow creates separate canonical keys for matching.

- Reviewed cleaning rules are read from `data/reviewed/name_cleaning_rules.json`.
- Reviewed person-level corrections are read from `persona_name_overrides_v1.csv` and `persona_gender_overrides_v1.csv`.
- The current frequency and rarity reference is `name_frequency_analysis_v13.csv`.
- Rule cycles are resolved using observed frequency as the first tie-breaker and alphabetical order only as a deterministic second tie-breaker. The validation report records seven resolved cycles and zero remaining cycles.

This approach corrects known transcription/data-entry problems for linkage while retaining the original historical spelling for research.

### 2. Spanish spelling and accent rules

The name-reference stage creates comparison keys that support approved spelling logic:

- Diacritical marks are removed for matching. For example, `estévan` and `estevan` compare as the same key, while the source spelling remains visible.
- Spanish `ce/se` and `ci/si` variants are recognized as matching evidence only in the approved phonetic context. Examples include `nepomuceno/nepomuseno` and `dionicio/dionisio/dioniscio`.
- Approved spelling variants are applied only through `approved_name_variant_mappings_v1.csv`; their applications are recorded in the reports package.
- The Oseas Bendezú correction and Barbara Orosco gender correction are handled through reviewed person-level override files rather than by silently editing raw records.

### 3. Name frequency and rarity

Name frequency is evidence, not proof of identity.

- Rare and very rare canonical names strengthen a candidate pair.
- Common names require corroboration from relatives, spouse, dates, roles, place, or other context.
- Variant spellings are grouped for frequency comparison only after a reviewed rule exists; the raw spellings are never erased.
- New uncertain spelling variants are placed in a review shortlist. They are not automatically merged.

### 4. Conservative candidate-generation rules

Notebook 02 adds comparison pairs through four blocking routes. Each route uses a maximum block size of 12 to prevent large common-name blocks from creating excessive or weak comparisons.

| Candidate route | Required evidence |
| --- | --- |
| Rare canonical full name | Canonical first and last name, with a rare or very rare first name. |
| Canonical name plus parents | Canonical full name and the same cleaned parent pair. |
| Canonical name plus spouse | Canonical full name and the same cleaned spouse name. |
| Marriage godparent rescue | Canonical full name and normalized place, with at least one appearance in a marriage-godparent role. |

The new candidate set is kept separate from the original candidate universe. Original pairs remain unchanged, previously confirmed review pairs are retained, and a 50,000-pair safety ceiling prevents runaway expansion.

### 5. Candidate safeguards and contradictions

Before a new candidate can enter the v2 review set, the workflow excludes these incompatible patterns:

- the same persona compared with itself;
- the same event and the same role on both sides;
- explicit male/female gender conflict;
- a pair more than 80 event years apart within the narrow name-enhancement route;
- two baptized-person appearances more than one year apart;
- a person acting as a witness or godparent before their own baptism or fewer than 12 years after it;
- the same named parent/spouse couple having child baptisms 50 or more years apart.

The last safeguard was added after the Manuela Huamani/Guamani example. It avoids treating two same-named couples with children decades apart as one family. Every exclusion reason is written to `name_enhanced_safeguard_rejections_v2.csv`.

Chronology is also handled more broadly in `config/prl_rules.yaml`: dates such as an uncertain marriage/baptism gap are flagged for manual review rather than treated as a universal automatic rejection. The >80-year rule above is only a narrow admission ceiling for the name-enhancement candidate route.

### 6. Gender, role, relative, and place evidence

The workflow uses context alongside a name match:

- Father/husband/godfather evidence supports male gender; mother/wife/godmother evidence supports female gender. A role-first gender-enriched output is created separately and disagreements are audited.
- Parent-pair agreement and spouse-name agreement are high-value review evidence.
- Exact normalized place agreement is supporting evidence only. It raises the review priority but cannot create or merge a pair by itself.
- Same-event/same-role duplicates and contradictory gender evidence are not allowed into the added candidate set.

### 7. Godparent and witness rule

The project distinguishes family relationships from social/religious roles.

- Marriage godparents were added as a candidate-retrieval route because they were previously absent from part of the comparison pool.
- The initial historical safeguard requires the service role to occur at least 12 years after the person's own baptism.
- The later restricted godparent stage is stricter: it considers only securely deduplicated multi-record people and requires age evidence of at least 13 years.
- Godparent candidates are scored and ranked for review, but they do not automatically alter identity clusters or family clusters.

This prevents a rare name in a godparent role from being treated as a confirmed person match without corroborating identity evidence.

### 8. Sibling-discovery rule

The sibling rule implements the documented shared-parent method:

1. Start from a bride or groom in a marriage record with identified parents and a usable birth-date estimate.
2. Search baptism records for children with the same parent pair.
3. Retain possible siblings within an approximate ±15-year window.
4. Allow births before a later marriage, because the historical record may include children born before the parents married.

The rule creates a review-only queue. It currently contains 480 candidates, with 452 cases in the sibling-and-parent review report. No sibling candidate has been automatically merged into the safe identity or family graph.

### 9. Model and review controls

- Reviewed decisions are preserved and checked against the candidate universe.
- Protected name-variant cases are excluded from training and used only for evaluation.
- Models are trained on established historical labels, then used to create review tiers rather than unconditional merges.
- Review queues preserve the pair key, original names, canonical evidence, dates, roles, relatives, safeguards, and reviewer notes.

### 10. Safe identity and family-cluster release

The final family graph uses only safe identity memberships and trusted parent-child or spouse relationships.

- Identity and family identifiers remain stable in the safe release.
- Review-only expanded, godparent, sibling, and duplicate-within-family candidates are excluded.
- The release validation reports 16,281 trusted relationships and zero relationships crossing family-cluster boundaries.
- Every source persona can be traced through the source-persona-to-identity-and-family audit table.

## Implemented outputs

| Output | Purpose |
| --- | --- |
| `research_data/02_name_frequency_analysis_v13.csv` | Reviewed name frequency and rarity reference. |
| `research_data/03_source_persona_safe_identity_family_membership_v3.csv` | Current source-persona to safe identity and family-cluster membership. |
| `research_data/04_safe_identity_people_nodes.csv` | One row per safe identity person for graph tools. |
| `research_data/04_trusted_family_relationships.csv` | Trusted parent-child and spouse relationships only. |
| `research_data/04_source_persona_to_identity_and_family_audit.csv` | Provenance trace from source persona to identity and family cluster. |
| `research_data/06_expanded_candidates_high_priority_review.csv` | Ranked expanded candidates requiring human review. |
| `research_data/07_potential_siblings_with_parents_review.csv` | Review-only sibling candidates and their parent evidence. |
| `research_data/08_family_cluster_release_readiness.csv` | Release metrics and safe-family validation gate. |

## Folder guide

| Folder | Purpose |
| --- | --- |
| `notebooks/` | Current three-notebook research workflow. |
| `notebooks/archive/` | Superseded work retained for provenance; do not run by default. |
| `scripts/` | Reusable utilities for review packages, exports, graph files, and audits. |
| `research_data/` | Curated CSV package for the internal research team. |
| `data/` | Local source, reviewed, interim, and processed project data. |
| `outputs/` | Local reports, review queues, graphs, GEDCOM exports, and diagrams. |
| `config/` | Project linkage-rule configuration. |

## Visualizing safe family clusters

Trusted family connections can be viewed through yEd, Neo4j, Gephi, or GEDCOM-compatible genealogy tools. For a compact yEd example, open:

`outputs/yed/selected_demo_families.graphml`

This file contains three trusted demonstration family clusters. The larger `safe_family_connections_all.graphml` is useful as an atlas but may be slow because it contains every connected safe family relationship.

## Status and next steps

The current safe release is ready for controlled research use and family-cluster lookup. It is intentionally conservative, not a complete genealogy. Future work should review held candidates, approve new rules only with documented evidence, and compare validation results after each rerun.

For the full current status, see `PROJECT_STATUS.md`.
