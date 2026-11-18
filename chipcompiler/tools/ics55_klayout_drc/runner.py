#!/usr/bin/env python
"""Run the standalone ICS55 full-mask DRC engine for an ECC step."""

from pathlib import Path

from chipcompiler.data import StepEnum, Workspace, WorkspaceStep
from chipcompiler.tools.ics55_klayout_drc import artifacts, bridge

_CONFIG_KEY = StepEnum.MASK_DRC.value


def _config_path(workspace: Workspace) -> Path:
    path = (workspace.config or {}).get(_CONFIG_KEY)
    if path is None:
        from chipcompiler.data import build_workspace_config_paths

        workspace.config = build_workspace_config_paths(workspace)
        path = workspace.config[_CONFIG_KEY]
    return Path(path)


def _read_config(workspace: Workspace) -> dict:
    from chipcompiler.utility import json_read

    config = json_read(_config_path(workspace))
    return config if isinstance(config, dict) else {}


def _data_dir(step: WorkspaceStep) -> Path:
    data_dir = (step.data.steps or {}).get(step.name) or step.data.dir
    if data_dir is None:
        raise ValueError("mask_drc data directory is not configured")
    return Path(data_dir)


def _layout_candidates(workspace: Workspace, step: WorkspaceStep, config: dict):
    configured = str(config.get("layout") or "").strip()
    if configured:
        path = Path(configured).expanduser()
        if not path.is_absolute() and workspace.directory:
            path = Path(workspace.directory) / path
        yield path
        return
    if step.output.gds:
        yield Path(step.output.gds)
    if step.input.def_:
        predecessor = Path(step.input.def_).parent
        for pattern in ("*.gds", "*.oas"):
            for path in sorted(
                predecessor.glob(pattern),
                key=lambda item: item.stat().st_mtime,
                reverse=True,
            ):
                yield path


def _resolve_layout(workspace: Workspace, step: WorkspaceStep, config: dict) -> Path | None:
    for candidate in _layout_candidates(workspace, step, config):
        if candidate.is_file():
            return candidate
    return None


def _engine_config(engine, pdk, workspace: Workspace, config: dict):
    pdk_root = config.get("pdk_root") or getattr(workspace.pdk, "root", None) or None
    cfg = pdk.load_pdk_config(pdk.DEFAULT_CONFIG, pdk_root=pdk_root)
    stack = config.get("stack") or {}
    if isinstance(stack, dict) and stack:
        cfg.stack = {key: int(stack.get(key, cfg.stack[key])) for key in pdk.STACK_KEYS}
        cfg.validate_stack()
    switches = {
        key: bool(value)
        for key, value in (config.get("switches") or {}).items()
        if key in engine.SWITCH_KEYS
    }
    return cfg, switches


def run_step(
    workspace: Workspace,
    step: WorkspaceStep,
    ecc_module=None,
) -> bool:
    """Run KLayout mask DRC; the native ecc-tools DRC step is untouched."""
    logger = workspace.logger
    try:
        engine, pdk, report = bridge.load_api()
    except Exception as exc:
        logger.error("mask_drc: cannot load the standalone KLayout DRC package: %s", exc)
        return False

    try:
        config = _read_config(workspace)
        layout = _resolve_layout(workspace, step, config)
        if layout is None:
            logger.error(
                "mask_drc: no GDS/OASIS layout found for %s",
                step.output.gds or step.input.def_ or "the workspace",
            )
            return False
        cfg, switches = _engine_config(engine, pdk, workspace, config)
        data_dir = _data_dir(step)
        result = engine.run_drc(
            layout,
            data_dir,
            cfg,
            top=config.get("top") or workspace.design.top_module or None,
            klayout=config.get("klayout") or None,
            overrides=switches,
            threads=config.get("threads") or None,
        )
        report.write_reports(data_dir, result.summary_data, result.violations)
        violations = artifacts.load_violation_map(data_dir)
        if not artifacts.write_feature(step, violations):
            logger.error("mask_drc: failed to write %s", step.feature.step)
            return False
        if not artifacts.write_metrics(step, result, layout):
            logger.error("mask_drc: failed to write %s", step.analysis.metrics)
            return False
        if not artifacts.write_qor_summary(step, len(violations)):
            logger.error("mask_drc: failed to write %s", step.analysis.qor_summary)
            return False
        artifacts.copy_reports(step, data_dir)
    except (engine.EngineError, ValueError, OSError) as exc:
        logger.error("mask_drc failed: %s", exc)
        return False

    if workspace.directory:
        from chipcompiler.tools.ecc.signoff_checklist import refresh_step_checklist

        if not refresh_step_checklist(workspace, step):
            logger.warning("mask_drc checklist reports blocking items")

    if result.violation_count:
        logger.warning(
            "mask_drc: %d violations across %d rules (report %s)",
            result.violation_count,
            result.rules_with_violations,
            data_dir / "drc_report.html",
        )
    else:
        logger.info(
            "mask_drc: clean after %d rule checks", result.summary_data.get("rules_checked", 0)
        )
    return True
