#!/usr/bin/env python3
"""Compatibility entry point for existing launcher/source-install workflows."""
from pathlib import Path
import runpy
import sys
if __name__ == "__main__":
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    runpy.run_module("scripts.build.build_from_rom", run_name="__main__")
