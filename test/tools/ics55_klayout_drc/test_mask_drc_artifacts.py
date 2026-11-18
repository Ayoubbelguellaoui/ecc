import json
from types import SimpleNamespace

from chipcompiler.data import StepEnum, Workspace
from chipcompiler.tools.ics55_klayout_drc import artifacts, builder

VIOLATIONS = [
    {
        "type": "MET1.W.1",
        "rule": "MET1.W.1",
        "layer": "MET1",
        "class": "error",
        "count": 1,
        "shape": [0.0, 0.0, 0.05, 1.0, "MET1"],
        "bbox": [0.0, 0.0, 0.05, 1.0],
    },
    {
        "type": "MET1.W.1",
        "rule": "MET1.W.1",
        "layer": "MET1",
        "class": "error",
        "count": 1,
        "shape": [2.0, 0.0, 2.05, 1.0, "MET1"],
        "bbox": [2.0, 0.0, 2.05, 1.0],
    },
]


def _step(tmp_path):
    workspace = Workspace(directory=tmp_path)
    workspace.design.name = "chip"
    workspace.pdk.root = tmp_path / "pdk"
    step = builder.build_step(
        workspace=workspace,
        step_name=StepEnum.MASK_DRC.value,
        input_def=None,
        input_verilog=None,
    )
    builder.build_step_space(step)
    return step


def test_distribution_groups_by_rule_and_layer():
    assert artifacts.build_distribution(VIOLATIONS) == {
        "MET1.W.1": {"layers": {"MET1": {"number": 2}}}
    }


def test_feature_and_qor_summary_use_the_ecc_schema(tmp_path):
    step = _step(tmp_path)

    assert artifacts.write_feature(step, VIOLATIONS) is True
    assert artifacts.write_qor_summary(step, len(VIOLATIONS)) is True

    feature = json.loads(step.feature.step.read_text())
    assert feature == {
        "drc": {
            "number": 2,
            "distribution": {"MET1.W.1": {"layers": {"MET1": {"number": 2}}}},
        }
    }

    summary = json.loads(step.analysis.qor_summary.read_text())
    gate = summary["gates"][0]
    assert summary["schema_version"] == 4
    assert gate["id"] == "qor.mask_drc.clean"
    assert gate["state"] == "failed"
    assert gate["metrics"] == [
        {"id": "mask_drc_count", "actual": 2, "operator": "==", "expected": 0}
    ]


def test_metrics_record_counts_and_engine(tmp_path):
    step = _step(tmp_path)
    result = SimpleNamespace(
        status="violations",
        command=["/usr/bin/klayout", "-b"],
        summary_data={
            "violations": 2,
            "rules_checked": 185,
            "rules_with_violations": 1,
            "skipped": [],
            "notes": ["MOM deferred"],
            "top": "TOP",
        },
    )

    assert artifacts.write_metrics(step, result, tmp_path / "chip.gds") is True

    metrics = json.loads(step.analysis.metrics.read_text())
    assert metrics["drc_num"] == 2
    assert metrics["rules_checked"] == 185
    assert metrics["by_class"] == {"error": 2}
    assert metrics["klayout"] == "/usr/bin/klayout"
    assert metrics["notes"] == ["MOM deferred"]
