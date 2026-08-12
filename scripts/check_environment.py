#!/usr/bin/env python3
"""Print a compact and machine-readable development-environment baseline."""

from __future__ import annotations

import json
import os
import platform
import shutil
import subprocess
import sys
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PACKAGES = ["mcpmodel", "jsonschema", "PyYAML", "numpy", "pandas", "scikit-learn", "pytest", "ruff"]


def package_versions() -> dict[str, str]:
    result = {}
    for package in PACKAGES:
        try:
            result[package] = version(package)
        except PackageNotFoundError:
            result[package] = "not-installed"
    return result


def git_value(*args: str) -> str:
    process = subprocess.run(
        ["git", *args], cwd=ROOT, check=False, capture_output=True, text=True
    )
    return process.stdout.strip() or "unavailable"


def main() -> int:
    disk = shutil.disk_usage(ROOT)
    report = {
        "project_root": str(ROOT),
        "python": sys.version.split()[0],
        "executable": sys.executable,
        "platform": platform.platform(),
        "cpu_count": os.cpu_count(),
        "disk_free_gib": round(disk.free / 1024**3, 2),
        "git_commit": git_value("rev-parse", "HEAD"),
        "git_status": git_value("status", "--short"),
        "thread_limits": {
            name: os.getenv(name, "unset")
            for name in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS")
        },
        "packages": package_versions(),
    }
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if sys.version_info >= (3, 11) else 1


if __name__ == "__main__":
    raise SystemExit(main())
