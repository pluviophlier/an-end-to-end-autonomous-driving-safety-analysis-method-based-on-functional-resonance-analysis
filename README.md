# FRAM safety analysis for an end-to-end driving case study

[中文说明](README.zh-CN.md)

This is a compact release of the **FRAM modeling and variability propagation
experiment** associated with:

> Tang, S. et al., “An End-to-End Autonomous Driving Safety Analysis Method
> Based on Functional Resonance Analysis,” *Proceedings of the 19th
> International Forum of Automotive Traffic Safety*, ATS.2025.302, 2025.

It contains the two FRAM models and their edge weights. It does **not** contain
VAD training code, NuScenes data, driving images, or trained network weights.
Those items are outside the scope of this analysis code.

## Run

Use Python 3.12 or later. The analysis uses only the Python standard library.
From this repository's root, run:

```sh
python scripts/reproduce.py
python -m unittest discover -s tests -v
```

The first command validates each model against its weight table and writes
`results/summary.csv`, `results/distribution.csv`, and
`results/provenance.json`. Results are computed from the checked-in models;
there is no need to download or generate a large instance-level JSON file.

## Inputs and calculation

| Case | FRAM model | Edge weights | Size |
| --- | --- | --- | --- |
| Original | `models/original.xfmv` | `configs/original_weights.csv` | 25 functions, 33 edges |
| With mitigation | `models/mitigated.xfmv` | `configs/mitigated_weights.csv` | 30 functions, 38 edges |

The target is function 19, “Trajectory Tracking Control.” The analysis follows
input, control, and precondition edges. Each relevant non-target function has
an independent, equally weighted endogenous variation of 0, 1, or 2. In the
mitigated model, functions 25–29 have endogenous variation fixed at 0. A
function's total variation is its endogenous variation plus the weighted sum
of its predecessors' total variation. The target has no endogenous variation.
These explicit assumptions allow the target distribution to be computed
exactly by convolution without listing every combination. The program rejects
cycles and any mismatch between a model and its weight table.

## Relationship to the published numbers

**This repository is a transparent reconstruction, not a verified reproduction
of every number in the paper.** With the source files available here, the
original model has mean 33.00, matching Table 6, but its computed maximum is
66.00 versus the reported 64.00. The mitigated model has mean 29.6875, whereas
Table 6 reports 24.20. The paper describes mitigation
weights of 0.1, while the surviving mitigated CSV assigns 0.5 to nine edges.
The old mitigated results file also identifies a 25-function, 33-edge model,
which is the size of the original model rather than the 30-function,
38-edge mitigated model. Its model path points to a different file.

The previous scripts capped enumeration and sampled combinations. Their
output should therefore not be described as exhaustive. The exact method in
this repository has different, documented assumptions; `provenance.json`
records its inputs, file hashes, and deviations from Table 6. Do not use the
mitigated result as confirmation of the paper's reported effect until the
original run configuration is recovered and checked.

## License

The repository is released under the Apache License 2.0. See `LICENSE`.
