import json
import shutil
import subprocess
from pathlib import Path

import pytest

from chipcompiler.data import StepEnum, Workspace, build_workspace_config_paths
from chipcompiler.tools.ics55_klayout_drc import bridge, builder, runner

PDK_ROOT = Path(__file__).resolve().parents[4] / "icsprout55-pdk"

pytestmark = pytest.mark.skipif(
    not bridge.is_available() or not PDK_ROOT.is_dir(),
    reason="KLayout and the ICS55 PDK are required",
)


def _make_gds(path: Path, body: str = "") -> None:
    script = path.with_suffix(".rb")
    script.write_text(
        "ly = RBA::Layout.new\n"
        'top = ly.create_cell("TOP")\n'
        f"{body}\n"
        f"ly.write('{path.as_posix()}')\n",
        encoding="utf-8",
    )
    subprocess.run(
        [shutil.which("klayout"), "-b", "-r", str(script)],
        check=True,
        capture_output=True,
        text=True,
    )


def _step(tmp_path, layout: Path):
    workspace = Workspace(directory=tmp_path / "workspace")
    workspace.design.name = "chip"
    workspace.design.top_module = "TOP"
    workspace.pdk.root = PDK_ROOT
    workspace.config = build_workspace_config_paths(workspace)
    step = builder.build_step(
        workspace=workspace,
        step_name=StepEnum.MASK_DRC.value,
        input_def=None,
        input_verilog=None,
        output_gds=layout,
    )
    builder.build_step_space(step)
    builder.build_step_config(workspace, step)
    return workspace, step


def test_run_step_writes_mask_drc_artifacts(tmp_path):
    layout = tmp_path / "clean.gds"
    _make_gds(layout)
    workspace, step = _step(tmp_path, layout)

    assert runner.run_step(workspace, step) is True

    data_dir = step.data.steps[StepEnum.MASK_DRC.value]
    assert json.loads((data_dir / "violation_map.json").read_text()) == []
    feature = json.loads(step.feature.step.read_text())
    assert feature["drc"]["number"] == 0
    metrics = json.loads(step.analysis.metrics.read_text())
    assert metrics["drc_num"] == 0
    assert metrics["rules_checked"] > 100
    summary = json.loads(step.analysis.qor_summary.read_text())
    assert summary["gates"][0]["state"] == "pass"
    assert (step.report.dir / "mask_drc.lyrdb").is_file()
    assert (step.report.dir / "mask_drc_report.html").is_file()


def test_run_step_records_violations_without_failing_the_run(tmp_path):
    layout = tmp_path / "bad.gds"
    _make_gds(
        layout,
        "m1 = ly.layer(81, 1)\n"
        "top.shapes(m1).insert(RBA::Box.new(0, 0, 50, 1000))",
    )
    workspace, step = _step(tmp_path, layout)

    assert runner.run_step(workspace, step) is True

    feature = json.loads(step.feature.step.read_text())
    assert feature["drc"]["number"] > 0
    assert "MET1.W.1" in feature["drc"]["distribution"]
    summary = json.loads(step.analysis.qor_summary.read_text())
    assert summary["gates"][0]["state"] == "failed"
