"""Build the compact active name-linkage workflow notebook.

This is intentionally non-destructive: it writes a new consolidated notebook;
the caller archives source notebooks only after the result validates.
"""

from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
NOTEBOOKS = ROOT / "notebooks"
BASE = NOTEBOOKS / "03_name_review_and_label_validation.ipynb"
EXTRAS = [
    NOTEBOOKS / "04_name_variant_curation.ipynb",
    NOTEBOOKS / "05_prepare_name_variant_linkage_evaluation.ipynb",
    NOTEBOOKS / "06_score_name_variant_pairs_with_locked_model.ipynb",
    NOTEBOOKS / "07_prepare_canonical_feature_regression_dataset.ipynb",
    NOTEBOOKS / "08_prepare_canonical_model_training_input.ipynb",
    NOTEBOOKS / "09_evaluate_canonical_feature_calibration_v4.ipynb",
]
OUTPUT = NOTEBOOKS / "03_name_review_and_model_evaluation.ipynb"


def load(path: Path) -> dict:
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


base = load(BASE)
cells = list(base["cells"])

for path in EXTRAS:
    extra = load(path)
    cells.append({
        "cell_type": "markdown",
        "metadata": {},
        "source": [
            "---\n",
            f"## Consolidated section: {path.stem}\n",
            "\n",
            "Run this section only when its stated inputs have been created. "
            "It does not replace source records or identity clusters.\n",
        ],
    })
    cells.extend(extra["cells"])

base["cells"] = cells
with OUTPUT.open("w", encoding="utf-8", newline="\n") as handle:
    json.dump(base, handle, ensure_ascii=False, indent=1)
    handle.write("\n")

print(f"Created {OUTPUT}")
print(f"Cells: {len(cells)}")
