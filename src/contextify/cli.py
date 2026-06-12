"""Console entry point for the contextify CLI."""

from __future__ import annotations

from contextify.exporter import main


def entry() -> None:
    raise SystemExit(main())
