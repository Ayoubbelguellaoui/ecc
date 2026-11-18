#!/usr/bin/env python

from chipcompiler.tools.ics55_klayout_drc.bridge import is_available


def is_eda_exist() -> bool:
    """Check that KLayout and the standalone ICS55 deck are available."""
    return is_available()
