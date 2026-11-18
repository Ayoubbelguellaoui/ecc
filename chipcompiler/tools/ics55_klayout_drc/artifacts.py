#!/usr/bin/env python
"""ECC-facing artifacts derived from the standalone mask DRC run."""

import json
import shutil
from pathlib import Path

from chipcompiler.data import EccStep
from chipcompiler.utility import json_read, json_write

FEATURE_SCHEMA = {"number": 0, "distribution": {}}
REPORT_COPIES = {
    "drc.lyrdb": "mask_drc.lyrdb",
    "drc_summary.json": "mask_drc_summary.json",
    "drc_summary.csv": "mask_drc_summary.csv",
    "drc_report.html": "mask_drc_report.html",
    "drc.log": "mask_drc.log",
}


def load_violation_map(data_dir: Path | str) -> list[dict]:
    path = Path(data_dir) / "violation_map.json"
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        return []
    return payload if isinstance(payload, list) else []


def build_distribution(violations: list[dict]) -> dict:
    distribution = {}
    for violation in violations:
        if not isinstance(violation, dict):
            continue
        rule = violation.get("type") or violation.get("rule")
        if not isinstance(rule, str) or not rule:
            continue
        shape = violation.get("shape")
        layer = shape[4] if isinstance(shape, list) and len(shape) >= 5 else None
        layer = str(layer or violation.get("layer") or "UNKNOWN")
        layers = distribution.setdefault(rule, {"layers": {}})["layers"]
        layers.setdefault(layer, {"number": 0})["number"] += 1
    return distribution


def write_feature(step: EccStep, violations: list[dict]) -> bool:
    payload = {
        "drc": {
            "number": len(violations),
            "distribution": build_distribution(violations),
        }
    }
    return json_write(step.feature.step, payload)


def write_metrics(step: EccStep, result, layout: Path) -> bool:
    summary = result.summary_data or {}
    count = int(summary.get("violations") or 0)
    payload = {
        "drc_num": count,
        "status": result.status,
        "rules_checked": int(summary.get("rules_checked") or 0),
        "rules_with_violations": int(summary.get("rules_with_violations") or 0),
        "by_class": {"error": count},
        "layout": str(layout),
        "top": summary.get("top") or "",
        "klayout": result.command[0] if result.command else "",
        "skipped": list(summary.get("skipped") or []),
        "notes": list(summary.get("notes") or []),
    }
    return json_write(step.analysis.metrics, payload)


def write_qor_summary(step: EccStep, count: int) -> bool:
    gate = {
        "id": "qor.mask_drc.clean",
        "state": "pass" if count == 0 else "failed",
        "title": "Mask DRC clean",
        "metrics": [
            {
                "id": "mask_drc_count",
                "actual": count,
                "operator": "==",
                "expected": 0,
            }
        ],
        "evidence": [{"kind": "feature", "path": "data/drc/violation_map.json"}],
    }
    return json_write(
        step.analysis.qor_summary,
        {"schema_version": 4, "gates": [gate]},
    )


def copy_reports(step: EccStep, data_dir: Path | str) -> list[Path]:
    source_dir = Path(data_dir)
    report_dir = Path(step.report.dir)
    report_dir.mkdir(parents=True, exist_ok=True)
    copies = []
    for source_name, target_name in REPORT_COPIES.items():
        source = source_dir / source_name
        if not source.is_file():
            continue
        target = report_dir / target_name
        shutil.copy2(source, target)
        copies.append(target)
    return copies
