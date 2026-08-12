"""Atomic run directories and compact reproduction manifests."""

from __future__ import annotations

import hashlib
import importlib.metadata
import json
import platform
import shutil
import subprocess
import sys
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


@contextmanager
def atomic_run_directory(output_dir: Path) -> Iterator[Path]:
    """Build a run beside its destination and publish it with one rename."""
    if output_dir.exists():
        raise FileExistsError(f"run output already exists: {output_dir}")
    output_dir.parent.mkdir(parents=True, exist_ok=True)
    temporary = output_dir.with_name(f".{output_dir.name}.tmp-{uuid4().hex}")
    temporary.mkdir()
    try:
        yield temporary
        temporary.replace(output_dir)
    except BaseException:
        shutil.rmtree(temporary, ignore_errors=True)
        raise


def _git_commit(repository_root: Path) -> str | None:
    result = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=repository_root,
        capture_output=True,
        check=False,
        text=True,
    )
    return result.stdout.strip() if result.returncode == 0 else None


def write_reproduction_manifest(
    output_dir: Path,
    *,
    repository_root: Path,
    input_artifacts: dict[str, Path],
    config_artifacts: dict[str, Path],
) -> dict[str, object]:
    config_snapshot = output_dir / "config-snapshot"
    config_snapshot.mkdir()
    for name, path in config_artifacts.items():
        shutil.copy2(path, config_snapshot / name)
    packages = {}
    for name in ("numpy", "scipy", "scikit-learn", "joblib", "PyYAML"):
        try:
            packages[name] = importlib.metadata.version(name)
        except importlib.metadata.PackageNotFoundError:
            packages[name] = None
    manifest: dict[str, object] = {
        "created_at": datetime.now(UTC).isoformat(),
        "git_commit": _git_commit(repository_root),
        "python": sys.version,
        "platform": platform.platform(),
        "packages": packages,
        "inputs": {
            name: {"path": path.as_posix(), "sha256": sha256_file(path)}
            for name, path in sorted(input_artifacts.items())
        },
        "configs": {
            name: {"path": path.as_posix(), "sha256": sha256_file(path)}
            for name, path in sorted(config_artifacts.items())
        },
    }
    (output_dir / "reproduction-manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    return manifest
