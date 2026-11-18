import json
from pathlib import Path

from agent.data.foundation.parsers.drc_parser import parse_drc_artifacts


def _write(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def test_mask_drc_stage_uses_its_own_artifact_paths(tmp_path: Path):
    stage = tmp_path / "mask_drc_ecc"
    _write(
        stage / "data" / "drc" / "violation_map.json",
        [
            {
                "type": "ACT.W.1",
                "rule": "ACT.W.1",
                "layer": "ACT",
                "shape": [0, 0, 50, 1000, "ACT"],
                "bbox": {"llx": 0, "lly": 0, "urx": 50, "ury": 1000},
                "count": 1,
                "class": "error",
            }
        ],
    )
    _write(
        stage / "analysis" / "mask_drc_metrics.json",
        {"Tool": "ics55_klayout_drc", "drc_num": 1},
    )

    parsed = parse_drc_artifacts(stage)

    assert parsed["available"] is True
    assert parsed["count"] == 1
    assert parsed["violations"][0]["type"] == "ACT.W.1"
    assert parsed["violations"][0]["layer"] == "ACT"
    assert parsed["violations"][0]["bbox"] == {"llx": 0.0, "lly": 0.0, "urx": 50.0, "ury": 1000.0}
    assert parsed["source"] == str(stage / "data" / "drc" / "violation_map.json")
    assert parsed["metrics_source"] == str(stage / "analysis" / "mask_drc_metrics.json")


def test_mask_drc_metrics_only_stage_is_available(tmp_path: Path):
    stage = tmp_path / "mask_drc_ecc"
    _write(stage / "analysis" / "mask_drc_metrics.json", {"drc_num": 7})

    parsed = parse_drc_artifacts(stage)

    assert parsed["available"] is True
    assert parsed["count"] == 7
    assert parsed["violations"] == []


def test_legacy_drc_stage_paths_are_unchanged(tmp_path: Path):
    stage = tmp_path / "drc_ecc"
    _write(stage / "data" / "drc" / "violation_map.json", [{"type": "short"}])
    _write(stage / "analysis" / "drc_metrics.json", {"drc_num": 1})

    parsed = parse_drc_artifacts(stage)

    assert parsed["count"] == 1
    assert parsed["violations"][0]["null_reason"] == {"bbox": "missing_violation_bbox"}
