#!/usr/bin/env python
"""Build the ECC mask_drc step backed by the standalone KLayout deck."""

import shutil
from pathlib import Path

from chipcompiler.data import (
    ChecklistState,
    EccAnalysis,
    EccData,
    EccFeature,
    EccOutput,
    EccReport,
    EccScript,
    EccStep,
    LogPaths,
    StepEnum,
    StepInput,
    SubflowState,
    Workspace,
    build_workspace_config_paths,
)
from chipcompiler.data.step import STEP_DIRECTORIES
from chipcompiler.tools.ics55_klayout_drc.bridge import template_config_path

TOOL = "ics55_klayout_drc"


def _chain_gds(input_def: Path | None) -> Path | None:
    """Return the GDS saved next to the predecessor DEF, if it follows convention."""
    if not input_def:
        return None
    path = Path(input_def)
    if path.name.endswith(".def.gz"):
        return path.with_name(path.name[: -len(".def.gz")] + ".gds")
    if path.suffix == ".def":
        return path.with_suffix(".gds")
    return None


def build_step(
    workspace: Workspace,
    step_name: str,
    input_def: Path | None,
    input_verilog: Path | None,
    input_db: Path | str | None = None,
    output_def: Path | None = None,
    output_verilog: Path | None = None,
    output_gds: Path | None = None,
    tool: str = TOOL,
    step_directory: Path | None = None,
) -> EccStep:
    """Build the mask_drc step without modifying the existing ecc DRC step."""
    directory = (
        Path(step_directory)
        if step_directory
        else Path(workspace.directory)
        / STEP_DIRECTORIES.get(step_name, f"{step_name}_{tool}")
    )
    design = workspace.design.name or "design"
    output_dir = directory / "output"
    data_dir = directory / "data"
    feature_dir = directory / "feature"
    report_dir = directory / "report"
    analysis_dir = directory / "analysis"

    layout = (
        Path(output_gds)
        if output_gds
        else _chain_gds(input_def) or output_dir / f"{design}_{step_name}.gds"
    )
    chain_def = (
        Path(output_def)
        if output_def
        else Path(input_def)
        if input_def
        else output_dir / f"{design}_{step_name}.def.gz"
    )
    chain_verilog = (
        Path(output_verilog)
        if output_verilog
        else Path(input_verilog)
        if input_verilog
        else output_dir / f"{design}_{step_name}.v.gz"
    )

    return EccStep(
        name=step_name,
        tool=tool,
        version="0.2",
        directory=directory,
        input=StepInput(
            def_=Path(input_def) if input_def else None,
            verilog=Path(input_verilog) if input_verilog else None,
            db=Path(input_db) if input_db else None,
        ),
        output=EccOutput(
            dir=output_dir,
            def_=chain_def,
            verilog=chain_verilog,
            gds=layout,
            db=Path(input_db) if input_db else "",
        ),
        data=EccData(
            dir=data_dir,
            steps={step_name: data_dir / "drc"},
        ),
        feature=EccFeature(
            dir=feature_dir,
            db=feature_dir / f"{step_name}.db.json",
            step=feature_dir / f"{step_name}.step.json",
            map=feature_dir / f"{step_name}.map.json",
        ),
        report=EccReport(
            dir=report_dir,
            db=report_dir / f"{step_name}.db.rpt",
            step=report_dir / f"{step_name}.rpt",
        ),
        log=LogPaths(
            dir=directory / "log",
            file=directory / "log" / f"{step_name}.log",
        ),
        script=EccScript(
            dir=directory / "script",
            main=directory / "script" / f"{step_name}_main.tcl",
        ),
        analysis=EccAnalysis(
            dir=analysis_dir,
            metrics=analysis_dir / "mask_drc_metrics.json",
            qor_metrics=analysis_dir / "qor_metrics.json",
            qor_summary=analysis_dir / "qor_summary.json",
            qor_hotspots=analysis_dir / "qor_hotspots.json",
            statis_csv=analysis_dir / f"{step_name}_statis.csv",
        ),
        subflow=SubflowState(path=directory / "subflow.json", steps=[]),
        checklist=ChecklistState(path=directory / "checklist.json", checklist=[]),
    )


def build_step_space(step: EccStep) -> None:
    for path in (
        step.directory,
        step.output.dir,
        step.data.dir,
        step.feature.dir,
        step.report.dir,
        step.log.dir,
        step.script.dir,
        step.analysis.dir,
    ):
        if path is not None:
            Path(path).mkdir(parents=True, exist_ok=True)
    for directory in step.data.iter_directories():
        Path(directory).mkdir(parents=True, exist_ok=True)


def build_step_config(workspace: Workspace, step: EccStep) -> None:
    """Ensure the step config exists before a run."""
    if not workspace.config:
        workspace.config = build_workspace_config_paths(workspace)
    config_path = workspace.config.get(StepEnum.MASK_DRC.value)
    if config_path is None:
        workspace.config = build_workspace_config_paths(workspace)
        config_path = workspace.config[StepEnum.MASK_DRC.value]
    config_path = Path(config_path)
    if config_path.is_file():
        return
    config_path.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(template_config_path(), config_path)
