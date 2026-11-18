import json

from chipcompiler.data import StepEnum, Workspace, build_workspace_config_paths
from chipcompiler.tools.ics55_klayout_drc import builder


def _workspace(tmp_path):
    workspace = Workspace(directory=tmp_path)
    workspace.design.name = "chip"
    workspace.design.top_module = "TOP"
    workspace.pdk.root = tmp_path / "pdk"
    return workspace


def test_build_step_keeps_the_layout_chain(tmp_path):
    workspace = _workspace(tmp_path)
    drc_def = tmp_path / "drc_ecc" / "output" / "chip_drc.def.gz"
    drc_verilog = tmp_path / "drc_ecc" / "output" / "chip_drc.v.gz"

    step = builder.build_step(
        workspace=workspace,
        step_name=StepEnum.MASK_DRC.value,
        input_def=drc_def,
        input_verilog=drc_verilog,
    )

    assert step.name == StepEnum.MASK_DRC.value
    assert step.tool == builder.TOOL
    assert step.directory == tmp_path / "mask_drc_ecc"
    assert step.data.steps[StepEnum.MASK_DRC.value] == tmp_path / "mask_drc_ecc" / "data" / "drc"
    assert step.output.def_ == drc_def
    assert step.output.verilog == drc_verilog
    assert step.output.gds == tmp_path / "drc_ecc" / "output" / "chip_drc.gds"


def test_build_step_space_and_config(tmp_path):
    workspace = _workspace(tmp_path)
    workspace.config = build_workspace_config_paths(workspace)
    step = builder.build_step(
        workspace=workspace,
        step_name=StepEnum.MASK_DRC.value,
        input_def=None,
        input_verilog=None,
    )

    builder.build_step_space(step)
    builder.build_step_config(workspace, step)

    assert step.output.dir.is_dir()
    assert step.data.steps[StepEnum.MASK_DRC.value].is_dir()
    assert step.report.dir.is_dir()
    config = json.loads(workspace.config[StepEnum.MASK_DRC.value].read_text())
    assert config["stack"]["total_metal"] == 6
    assert config["stack"]["T4V2_T4M2"] == 1
    assert config["switches"]["density"] is True
