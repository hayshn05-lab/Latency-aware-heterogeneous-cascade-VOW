"""Deterministic aggregate writers; raw source records never enter these files."""
from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Any


NAMES = ("data_manifest.json", "market_validation.csv", "event_bundles.csv", "delay_profile.csv", "first_print_latency.csv", "observations.csv", "summary.json", "latency_profile.svg", "generated_findings.md")


def _json(path: Path, value: Any) -> None:
    path.write_text(json.dumps(value, sort_keys=True, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def _csv(path: Path, rows: list[dict[str, Any]]) -> None:
    fields = sorted({key for row in rows for key in row})
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        for row in sorted(rows, key=lambda value: tuple(str(value.get(field, "")) for field in fields)):
            writer.writerow({field: "" if row.get(field) is None else row.get(field) for field in fields})


def _svg(delay_profile: list[dict[str, Any]]) -> str:
    values = [float(row["median_repricing_points"]) for row in delay_profile if row.get("median_repricing_points") is not None]
    ymax = max(values, default=1.0)
    points = []
    for index, row in enumerate(sorted(delay_profile, key=lambda item: item["horizon_seconds"])):
        value = row.get("median_repricing_points")
        if value is not None:
            points.append(f"{70 + index * 90},{190 - 140 * float(value) / ymax:.1f}")
    labels = "".join(f'<text x="{70 + index * 90}" y="220" text-anchor="middle">{row["horizon_seconds"]}s</text>' for index, row in enumerate(sorted(delay_profile, key=lambda item: item["horizon_seconds"])))
    coverage = "; ".join(f'{row["horizon_seconds"]}s: n={row.get("clean_eligible_pairs", 0)}, missing={row.get("missing_pairs", 0)}' for row in sorted(delay_profile, key=lambda item: item["horizon_seconds"]))
    return f'''<svg xmlns="http://www.w3.org/2000/svg" width="820" height="270" viewBox="0 0 820 270" role="img" aria-label="Median absolute repricing by delay; probability points; no smoothing">
<rect width="100%" height="100%" fill="white"/><text x="20" y="24" font-family="sans-serif" font-size="15">Median absolute repricing (probability points); common positional scale 0–{ymax:g}</text>
<line x1="55" y1="190" x2="790" y2="190" stroke="black"/><line x1="55" y1="45" x2="55" y2="190" stroke="black"/>
<polyline points="{' '.join(points)}" fill="none" stroke="#1769aa" stroke-width="2"/>{labels}
<text x="20" y="255" font-family="sans-serif" font-size="11">Sample size / missingness: {coverage or 'no eligible observations'}. Points are unsmoothed.</text></svg>'''


def write_outputs(output: Path, *, manifest: list[dict[str, Any]], market_validation: list[dict[str, Any]], bundles: list[dict[str, Any]], observations: list[dict[str, Any]], delay_profile: list[dict[str, Any]], first_print: list[dict[str, Any]], timestamp_precision: str = "seconds") -> None:
    output.mkdir(parents=True, exist_ok=True)
    _json(output / "data_manifest.json", manifest)
    _csv(output / "market_validation.csv", market_validation)
    _csv(output / "event_bundles.csv", bundles)
    _csv(output / "delay_profile.csv", delay_profile)
    _csv(output / "first_print_latency.csv", first_print)
    _csv(output / "observations.csv", observations)
    summary = {"economic_label": "non-executable price-move proxy", "interpretation_gate": "descriptively estimable only when timestamp precision and coverage support the requested delay", "timestamp_precision": timestamp_precision, "delay_rows": len(delay_profile), "observation_rows": len(observations)}
    _json(output / "summary.json", summary)
    (output / "latency_profile.svg").write_text(_svg(delay_profile), encoding="utf-8")
    milliseconds = "identifiable" if timestamp_precision == "milliseconds" else "not identifiable"
    (output / "generated_findings.md").write_text(f"# Pilot findings\n\nAll price results are **non-executable price-move proxy** measures, not profit, return, or realizable PnL. Missing values are not treated as zero. Source record precision: {timestamp_precision}; seconds and minutes are identifiable only to that precision; milliseconds are {milliseconds}.\n", encoding="utf-8")
