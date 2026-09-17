"""Validate FRAM inputs and compute a target node's exact discrete distribution.

Each active function has an independent endogenous value in {0, 1, 2}. A
function's total value is its endogenous value plus weighted predecessor
values. The target and specified mitigation functions have endogenous value 0.
The graph must be acyclic. These are explicit analysis assumptions, not a
claim that this implementation reproduces the paper's unpublished run setup.
"""

from __future__ import annotations

import csv
import heapq
import math
import xml.etree.ElementTree as ET
from collections import defaultdict
from fractions import Fraction
from pathlib import Path


ALLOWED_ASPECTS = frozenset({"I", "C", "P"})
LEVELS = (0, 1, 2)


def load_model(path: Path) -> tuple[dict[int, str], set[tuple[int, int, str]]]:
    root = ET.parse(path).getroot()
    functions = {
        int(item.findtext("IDNr")): item.findtext("IDName", "")
        for item in root.findall("./Functions/Function")
    }
    if not functions:
        raise ValueError(f"No FRAM functions in {path}")
    edges = set()
    aspects = root.findall("./Aspects/Aspect")
    for item in aspects:
        label = item.findtext("Name", "")
        parts = label.split("|")
        if len(parts) != 4:
            raise ValueError(f"Malformed FRAM aspect: {label!r}")
        source = int(item.attrib["outputFn"])
        target = int(item.attrib["toFn"])
        aspect = parts[3].strip().upper()
        if source not in functions or target not in functions:
            raise ValueError(f"Unknown function in FRAM aspect: {label!r}")
        edges.add((source, target, aspect))
    if len(edges) != len(aspects):
        raise ValueError("Model has duplicate source/target/aspect edges")
    return functions, edges


def load_weights(
    path: Path, model_edges: set[tuple[int, int, str]]
) -> dict[tuple[int, int, str], Fraction]:
    weights = {}
    with path.open(newline="", encoding="utf-8-sig") as stream:
        for row in csv.DictReader(stream):
            edge = (int(row["fromFn"]), int(row["toFn"]), row["toAspect"].strip().upper())
            if edge in weights:
                raise ValueError(f"Duplicate weight row: {edge}")
            value = Fraction(row["weight"].strip())
            if value < 0:
                raise ValueError(f"Negative edge weight: {edge}")
            weights[edge] = value
    missing = model_edges - weights.keys()
    extra = weights.keys() - model_edges
    if missing or extra:
        raise ValueError(f"Model/weight mismatch: missing={sorted(missing)}, extra={sorted(extra)}")
    return weights


def _topological_order(nodes: set[int], edges: dict) -> list[int]:
    indegree = {node: 0 for node in nodes}
    outgoing = defaultdict(list)
    for (source, target, _aspect), weight in edges.items():
        if source in nodes and target in nodes:
            outgoing[source].append((target, weight))
            indegree[target] += 1
    ready = [node for node, degree in indegree.items() if degree == 0]
    heapq.heapify(ready)
    order = []
    while ready:
        node = heapq.heappop(ready)
        order.append(node)
        for target, _ in outgoing[node]:
            indegree[target] -= 1
            if indegree[target] == 0:
                heapq.heappush(ready, target)
    if len(order) != len(nodes):
        raise ValueError("FRAM propagation graph contains a cycle")
    return order


def target_coefficients(
    functions: dict[int, str],
    weights: dict[tuple[int, int, str], Fraction],
    target: int = 19,
) -> dict[int, Fraction]:
    if target not in functions:
        raise ValueError(f"Target {target} is absent from the model")
    selected = {
        edge: weight for edge, weight in weights.items() if edge[2] in ALLOWED_ASPECTS
    }
    incoming = defaultdict(list)
    for (source, dest, _), weight in selected.items():
        incoming[dest].append((source, weight))
    ancestors = {target}
    pending = [target]
    while pending:
        for source, _ in incoming[pending.pop()]:
            if source not in ancestors:
                ancestors.add(source)
                pending.append(source)
    order = _topological_order(ancestors, selected)
    outgoing = defaultdict(list)
    for (source, dest, _), weight in selected.items():
        if source in ancestors and dest in ancestors:
            outgoing[source].append((dest, weight))
    coefficients = {target: Fraction(1)}
    for node in reversed(order):
        if node != target:
            coefficients[node] = sum(
                (weight * coefficients[dest] for dest, weight in outgoing[node]),
                Fraction(0),
            )
    return coefficients


def exact_distribution(coefficients: dict[int, Fraction], fixed_nodes: set[int], target: int = 19):
    variable = [node for node in sorted(coefficients) if node != target and node not in fixed_nodes]
    distribution = {Fraction(0): 1}
    for node in variable:
        coefficient = coefficients[node]
        next_distribution = defaultdict(int)
        for value, count in distribution.items():
            for level in LEVELS:
                next_distribution[value + coefficient * level] += count
        distribution = dict(next_distribution)
    return distribution, variable


def _value_at_rank(items: list[tuple[Fraction, int]], rank: int) -> Fraction:
    seen = 0
    for value, count in items:
        seen += count
        if rank < seen:
            return value
    raise ValueError("Rank exceeds distribution")


def describe(distribution: dict[Fraction, int]) -> dict[str, float | int]:
    items = sorted(distribution.items())
    count = sum(distribution.values())
    mean = sum((value * n for value, n in items), Fraction(0)) / count
    variance = sum(((value - mean) ** 2 * n for value, n in items), Fraction(0)) / count

    def quantile(q: Fraction) -> float:
        position = q * (count - 1)
        lower = position.numerator // position.denominator
        share = position - lower
        first = _value_at_rank(items, lower)
        second = _value_at_rank(items, min(lower + 1, count - 1))
        return float(first + share * (second - first))

    return {
        "combinations": count,
        "distinct_values": len(items),
        "mean": float(mean),
        "std": math.sqrt(float(variance)),
        "variance": float(variance),
        "min": float(items[0][0]),
        "p50": quantile(Fraction(1, 2)),
        "p95": quantile(Fraction(95, 100)),
        "max": float(items[-1][0]),
    }


def analyze(model_path: Path, weights_path: Path, fixed_nodes: set[int], target: int = 19):
    functions, model_edges = load_model(model_path)
    weights = load_weights(weights_path, model_edges)
    coefficients = target_coefficients(functions, weights, target)
    distribution, variable = exact_distribution(coefficients, fixed_nodes, target)
    summary = {
        "functions": len(functions),
        "edges": len(model_edges),
        "target_id": target,
        "target_name": functions[target],
        "variable_functions": len(variable),
        "fixed_functions": sorted(set(coefficients) & fixed_nodes),
        **describe(distribution),
    }
    return summary, distribution
