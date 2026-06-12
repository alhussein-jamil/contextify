"""Integration tests for the contextify export pipeline."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

from contextify import __version__
from contextify.exporter import main as export_main

FIXTURE_REPO = Path(__file__).parent / "fixtures" / "sample_repo"


def test_version_matches_pyproject() -> None:
    pyproject = (Path(__file__).parent.parent / "pyproject.toml").read_text(encoding="utf-8")
    assert f'version = "{__version__}"' in pyproject


def test_export_fixture_repo(tmp_path: Path) -> None:
    out = tmp_path / "bundle"
    code = export_main([str(FIXTURE_REPO), "-o", str(out), "-q"])
    assert code == 0

    context = out / "context.txt"
    stats = out / "statistics.json"
    assert context.is_file()
    assert stats.is_file()
    assert (out / "statistics.txt").is_file()

    text = context.read_text(encoding="utf-8")
    assert "=== src/hello.py" in text
    assert "def greet" in text
    assert "context_export/" not in text or ".contextifyignore" in text

    payload = json.loads(stats.read_text(encoding="utf-8"))
    assert payload["summary"]["text_files"] >= 2
    assert payload["summary"]["total_tokens"] > 0


def test_default_export_dir_is_cwd(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(tmp_path)
    out = tmp_path / "context_export"
    code = export_main([str(FIXTURE_REPO), "-q"])
    assert code == 0
    assert (out / "context.txt").is_file()
    assert not (FIXTURE_REPO / "context_export").exists()


def test_cli_entry_point(tmp_path: Path) -> None:
    out = tmp_path / "via_cli"
    proc = subprocess.run(
        [sys.executable, "-m", "contextify", str(FIXTURE_REPO), "-o", str(out), "-q"],
        capture_output=True,
        text=True,
        check=False,
    )
    assert proc.returncode == 0, proc.stderr
    assert (out / "context.txt").is_file()


def test_bundled_ignore_template_exists() -> None:
    from contextify.exporter import bundled_ignore_file

    path = bundled_ignore_file()
    assert path.is_file()
    assert path.name == "contextify.ignore"
    assert "context_export/" in path.read_text(encoding="utf-8")
