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
    def row_key(value: dict[str, Any]) -> tuple[Any, ...]:
        horizon = value.get("horizon_seconds")
        try:
            return (0, int(horizon), tuple(str(value.get(field, "")) for field in fields))
        except (TypeError, ValueError):
            return (1, 0, tuple(str(value.get(field, "")) for field in fields))
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        for row in sorted(rows, key=row_key):
            writer.writerow({field: "" if row.get(field) is None else row.get(field) for field in fields})


def _svg(delay_profile: list[dict[str, Any]]) -> str:
    ordered = sorted(delay_profile, key=lambda item: int(item["horizon_seconds"]))
    max_horizon = max((int(row["horizon_seconds"]) for row in ordered), default=1)
    points = []
    for row in ordered:
        value = row.get("updated_fraction")
        if value is not None:
            x = 70 + 700 * int(row["horizon_seconds"]) / max_horizon
            points.append(f"{x:.1f},{190 - 140 * float(value):.1f}")
    labels = "".join(f'<text x="{70 + 700 * int(row["horizon_seconds"]) / max_horizon:.1f}" y="220" text-anchor="middle">{row["horizon_seconds"]}s</text>' for row in ordered)
    def disclosure(row: dict[str, Any]) -> str:
        fraction = row.get("updated_fraction")
        updated = f"{100 * float(fraction):.1f}%" if fraction is not None else "NA"
        return f'{row["horizon_seconds"]}s | updated={updated} ({row.get("updated_pairs", "NA")}/{row.get("clean_eligible_pairs", 0)}) | clean eligible n={row.get("clean_eligible_pairs", 0)} | missing={row.get("missing_pairs", 0)}'
    details = "".join(f'<text x="20" y="{255 + index * 17}" font-family="sans-serif" font-size="11">{disclosure(row)}</text>' for index, row in enumerate(ordered))
    height = 275 + 17 * len(ordered)
    return f'''<svg xmlns="http://www.w3.org/2000/svg" width="820" height="{height}" viewBox="0 0 820 {height}" role="img" aria-label="Updated fraction by numeric delay; percent; unsmoothed">
<rect width="100%" height="100%" fill="white"/><text x="20" y="24" font-family="sans-serif" font-size="15">Updated fraction by delay (percent); unsmoothed</text>
<line x1="55" y1="190" x2="790" y2="190" stroke="black"/><line x1="55" y1="45" x2="55" y2="190" stroke="black"/>
<text x="48" y="194" text-anchor="end">0%</text><text x="48" y="124" text-anchor="end">50%</text><text x="48" y="54" text-anchor="end">100%</text>
<polyline points="{' '.join(points)}" fill="none" stroke="#1769aa" stroke-width="2"/>{labels}
{details}</svg>'''


def write_outputs(output: Path, *, manifest: list[dict[str, Any]], market_validation: list[dict[str, Any]], bundles: list[dict[str, Any]], observations: list[dict[str, Any]], delay_profile: list[dict[str, Any]], first_print: list[dict[str, Any]], timestamp_precision: dict[str, Any] | None = None) -> None:
    output.mkdir(parents=True, exist_ok=True)
    _json(output / "data_manifest.json", manifest)
    _csv(output / "market_validation.csv", market_validation)
    _csv(output / "event_bundles.csv", bundles)
    _csv(output / "delay_profile.csv", delay_profile)
    _csv(output / "first_print_latency.csv", first_print)
    _csv(output / "observations.csv", observations)
    precision = timestamp_precision or {"classification": "seconds", "milliseconds_identifiable": False, "least_fractional_digits": 0}
    summary = {"economic_label": "non-executable price-move proxy", "interpretation_gate": "descriptively estimable only when timestamp precision and coverage support the requested delay", "timestamp_precision": precision, "delay_rows": len(delay_profile), "observation_rows": len(observations), "headline_support": {"bundles": len(bundles), "markets": sum(row.get("decision") == "included" for row in market_validation), "observations": len(observations)}}
    _json(output / "summary.json", summary)
    (output / "latency_profile.svg").write_text(_svg(delay_profile), encoding="utf-8")
    milliseconds = "identifiable" if precision["milliseconds_identifiable"] else "not identifiable"
    timestamp_label = {"seconds": "second", "milliseconds": "millisecond"}.get(str(precision["classification"]), str(precision["classification"]))
    ordered = sorted(delay_profile, key=lambda row: int(row["horizon_seconds"]))
    coverage = "; ".join(f'{row["horizon_seconds"]}s: {100 * float(row["updated_fraction"]):.1f}% ({row.get("updated_pairs", "NA")}/{row.get("clean_eligible_pairs", 0)} clean eligible)' for row in ordered if row.get("updated_fraction") is not None) or "no clean eligible pairs"
    under_resolved = any(row.get("updated_fraction") is not None and float(row["updated_fraction"]) < 0.5 and float(row.get("median_delayed_age_seconds") or 0) >= 60 for row in ordered)
    resolution = "Because update coverage is sparse and delayed state age is high, seconds/minutes price-opportunity decay is weakly identified/under-resolved." if under_resolved else "Timestamp format alone does not establish seconds/minutes price-opportunity decay."
    (output / "generated_findings.md").write_text(f"# Pilot findings\n\nAll price results are **non-executable price-move proxy** measures, not profit, return, or realizable PnL. Remaining move is non-executable and not profit. Missing values are not treated as zero. Timestamps are {timestamp_label}-formatted; milliseconds are {milliseconds}.\n\nUpdated-trade coverage among clean eligible pairs: {coverage}. {resolution}\n", encoding="utf-8")


def write_audit_outputs(output: Path, manifest: list[dict[str, Any]], validation: list[dict[str, Any]], rows: list[dict[str, Any]]) -> None:
    output.mkdir(parents=True, exist_ok=True)
    _json(output / "audit_manifest.json", manifest)
    _csv(output / "market_validation.csv", validation)
    _csv(output / "orderbook_audit.csv", rows)
    _json(output / "audit_summary.json", {"markets_included": sum(row.get("decision") == "included" for row in validation), "token_audits": len(rows), "snapshots": sum(int(row["snapshot_count"]) for row in rows), "execution_verdict": "not execution-estimable without aligned order-book coverage and a fill model"})
