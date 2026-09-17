"""Run both published FRAM models without exporting individual combinations."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from fram_safety.analysis import analyze  # noqa: E402


INPUTS = {
    "original": ("models/original.xfmv", "configs/original_weights.csv", set()),
    "mitigated": (
        "models/mitigated.xfmv",
        "configs/mitigated_weights.csv",
        {25, 26, 27, 28, 29},
    ),
}
PAPER_TABLE_6 = {
    "original": {"mean": 33.00, "std": 9.07, "min": 0.00, "max": 64.00, "p95": 48.00},
    "mitigated": {"mean": 24.20, "std": 6.37, "min": 0.00, "max": 44.30, "p95": 34.40},
}


def file_hash(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, default=ROOT / "results")
    args = parser.parse_args()
    args.output_dir.mkdir(parents=True, exist_ok=True)

    summaries = []
    distributions = []
    inputs = {}
    comparisons = {}
    for name, (model_rel, weights_rel, fixed_nodes) in INPUTS.items():
        model = ROOT / model_rel
        weights = ROOT / weights_rel
        summary, distribution = analyze(model, weights, fixed_nodes)
        summaries.append({"model": name, **summary})
        distributions.extend(
            {"model": name, "value": str(value), "count": count}
            for value, count in sorted(distribution.items())
        )
        inputs[name] = {
            "model": model_rel,
            "model_sha256": file_hash(model),
            "weights": weights_rel,
            "weights_sha256": file_hash(weights),
        }
        comparisons[name] = {
            key: {"paper": expected, "computed": summary[key], "difference": round(summary[key] - expected, 6)}
            for key, expected in PAPER_TABLE_6[name].items()
        }
        print(f"{name}: {summary['functions']} functions, {summary['edges']} edges, "
              f"mean={summary['mean']:.4f}, std={summary['std']:.4f}, "
              f"p95={summary['p95']:.4f}")

    with (args.output_dir / "summary.csv").open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(summaries[0]))
        writer.writeheader()
        writer.writerows(summaries)
    with (args.output_dir / "distribution.csv").open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=("model", "value", "count"))
        writer.writeheader()
        writer.writerows(distributions)
    provenance = {
        "method": "Exact weighted distribution by convolution on an acyclic FRAM graph",
        "assumptions": {
            "endogenous_variation_levels": [0, 1, 2],
            "levels_equally_weighted_and_independent": True,
            "target_endogenous_variation": 0,
            "mitigation_function_endogenous_variation": 0,
            "aspects": ["C", "I", "P"],
            "edge_weights": "Use supplied CSV values without substitution",
        },
        "inputs": inputs,
        "paper_table_6_comparison": comparisons,
        "paper_table_6_reproduced": all(
            abs(item["difference"]) <= 0.02
            for model in comparisons.values()
            for item in model.values()
        ),
    }
    (args.output_dir / "provenance.json").write_text(
        json.dumps(provenance, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    if not provenance["paper_table_6_reproduced"]:
        print("Paper Table 6 differs from this reconstruction; see results/provenance.json.")


if __name__ == "__main__":
    main()
