#!/usr/bin/env python
"""Locate the standalone ics55_klayout_drc package from an ECC workspace."""

import os
import sys
from pathlib import Path

_ENV_ROOT = "ICS55_KLAYOUT_DRC_ROOT"
_PACKAGE = Path("src") / "ics55_klayout_drc"


def _checkout_candidates() -> tuple[Path, ...]:
    # <root>/ecc/chipcompiler/tools/ics55_klayout_drc/bridge.py
    here = Path(__file__).resolve()
    return (
        here.parents[4] / "ics55_klayout_drc",
        here.parents[3] / "ics55_klayout_drc",
    )


def _valid_root(path: Path) -> Path | None:
    candidate = Path(path).expanduser()
    return candidate.resolve() if (candidate / _PACKAGE).is_dir() else None


def standalone_root() -> Path | None:
    """Resolve the standalone checkout or an installed package."""
    env_root = os.environ.get(_ENV_ROOT)
    if env_root:
        root = _valid_root(Path(env_root))
        if root is not None:
            return root
    for candidate in _checkout_candidates():
        root = _valid_root(candidate)
        if root is not None:
            return root
    try:
        import ics55_klayout_drc
    except ImportError:
        return None
    return Path(ics55_klayout_drc.__file__).resolve().parents[2]


def load_api():
    """Return the standalone engine, pdk, and report modules."""
    root = standalone_root()
    if root is not None:
        source = root / "src"
        if source.is_dir() and str(source) not in sys.path:
            sys.path.insert(0, str(source))
    from ics55_klayout_drc import engine, pdk, report

    return engine, pdk, report


def is_available() -> bool:
    """True when the standalone deck and a KLayout executable are present."""
    try:
        engine, _pdk, _report = load_api()
        engine.find_klayout()
    except Exception:
        return False
    return engine.DECK_PATH.is_file()


def template_config_path() -> Path:
    return Path(__file__).resolve().parent / "configs" / "mask_drc_ecc.json"
