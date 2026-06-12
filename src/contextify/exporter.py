"""Core export engine for contextify."""

from __future__ import annotations

import argparse
import fnmatch
import hashlib
import io
import json
import logging
import mimetypes
import os
import re
import shutil
import sys
import time
from collections import Counter
from collections.abc import Iterable, Iterator
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Literal

# ---------------------------------------------------------------------------
# Optional Rich UI (graceful fallback to stdlib logging + simple progress)
# ---------------------------------------------------------------------------

try:
    from rich.console import Console
    from rich.logging import RichHandler
    from rich.progress import (
        BarColumn,
        MofNCompleteColumn,
        Progress,
        SpinnerColumn,
        TaskProgressColumn,
        TextColumn,
        TimeElapsedColumn,
        TimeRemainingColumn,
    )
    from rich.table import Table
    from rich.text import Text

    _RICH = True
except ImportError:  # pragma: no cover - exercised when rich is absent
    _RICH = False

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

PACKAGE_DIR = Path(__file__).resolve().parent
DEFAULT_EXPORT_DIRNAME = "context_export"
IGNORE_FILENAMES = (".contextifyignore",)


def is_frozen_binary() -> bool:
    return getattr(sys, "frozen", False)


def bundled_ignore_file() -> Path:
    """Path to the shipped default ignore template (works in wheel and PyInstaller)."""
    if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
        frozen = Path(sys._MEIPASS) / "contextify" / "contextify.ignore"
        if frozen.is_file():
            return frozen
    return PACKAGE_DIR / "contextify.ignore"


TEXT_EXTENSIONS = frozenset(
    {
        ".py",
        ".pyi",
        ".js",
        ".jsx",
        ".ts",
        ".tsx",
        ".mjs",
        ".cjs",
        ".json",
        ".jsonc",
        ".yaml",
        ".yml",
        ".toml",
        ".ini",
        ".cfg",
        ".conf",
        ".md",
        ".mdx",
        ".rst",
        ".txt",
        ".tex",
        ".bib",
        ".html",
        ".htm",
        ".xml",
        ".svg",
        ".css",
        ".scss",
        ".sass",
        ".less",
        ".sh",
        ".bash",
        ".zsh",
        ".fish",
        ".ps1",
        ".bat",
        ".cmd",
        ".sql",
        ".graphql",
        ".gql",
        ".proto",
        ".rs",
        ".go",
        ".java",
        ".kt",
        ".kts",
        ".c",
        ".h",
        ".cpp",
        ".hpp",
        ".cc",
        ".cxx",
        ".cs",
        ".rb",
        ".php",
        ".swift",
        ".scala",
        ".r",
        ".R",
        ".jl",
        ".lua",
        ".pl",
        ".pm",
        ".vim",
        ".el",
        ".clj",
        ".cljs",
        ".ex",
        ".exs",
        ".erl",
        ".hrl",
        ".hs",
        ".ml",
        ".mli",
        ".fs",
        ".fsx",
        ".dart",
        ".vue",
        ".svelte",
        ".astro",
        ".dockerfile",
        ".gitignore",
        ".gitattributes",
        ".editorconfig",
        ".env",
        ".env.example",
        ".csv",
        ".tsv",
        ".log",
        ".lock",
        ".cmake",
        ".make",
        ".mk",
        ".gradle",
        ".properties",
        ".mod",
        ".sum",
        ".nix",
        ".tf",
        ".tfvars",
        ".hcl",
        ".wasm",
        ".wat",
    }
)

MEDIA_EXTENSIONS = frozenset(
    {
        ".png",
        ".jpg",
        ".jpeg",
        ".gif",
        ".webp",
        ".bmp",
        ".ico",
        ".tiff",
        ".tif",
        ".avif",
        ".heic",
        ".heif",
        ".mp3",
        ".wav",
        ".flac",
        ".ogg",
        ".aac",
        ".m4a",
        ".wma",
        ".mp4",
        ".mkv",
        ".avi",
        ".mov",
        ".webm",
        ".wmv",
        ".flv",
        ".m4v",
        ".pdf",
        ".zip",
        ".tar",
        ".gz",
        ".bz2",
        ".xz",
        ".7z",
        ".rar",
        ".woff",
        ".woff2",
        ".ttf",
        ".otf",
        ".eot",
        ".exe",
        ".dll",
        ".so",
        ".dylib",
        ".bin",
        ".dat",
        ".npz",
        ".npy",
        ".pkl",
        ".pickle",
        ".pt",
        ".pth",
        ".onnx",
        ".parquet",
        ".feather",
        ".arrow",
        ".db",
        ".sqlite",
        ".sqlite3",
        ".blend",
        ".psd",
        ".ai",
        ".eps",
    }
)

FileKind = Literal["text", "binary", "skipped"]

SEPARATOR_MAJOR = "=" * 80
SECTION_BREAK = "---"

NAVIGATION_GUIDE = (
    "TREE below; INDEX is tab-separated (path/start/end/kind/lang/tokens); "
    'CONTENTS use "=== path ===" headers then raw source; binaries in assets/.'
)

LANGUAGE_BY_EXTENSION: dict[str, str] = {
    ".py": "Python",
    ".pyi": "Python",
    ".js": "JavaScript",
    ".jsx": "JavaScript",
    ".mjs": "JavaScript",
    ".cjs": "JavaScript",
    ".ts": "TypeScript",
    ".tsx": "TypeScript",
    ".json": "JSON",
    ".jsonc": "JSON",
    ".yaml": "YAML",
    ".yml": "YAML",
    ".toml": "TOML",
    ".md": "Markdown",
    ".mdx": "Markdown",
    ".rst": "reStructuredText",
    ".tex": "LaTeX",
    ".bib": "BibTeX",
    ".html": "HTML",
    ".htm": "HTML",
    ".xml": "XML",
    ".svg": "SVG",
    ".css": "CSS",
    ".scss": "SCSS",
    ".sass": "Sass",
    ".less": "Less",
    ".sh": "Shell",
    ".bash": "Shell",
    ".zsh": "Shell",
    ".fish": "Shell",
    ".ps1": "PowerShell",
    ".bat": "Batch",
    ".cmd": "Batch",
    ".sql": "SQL",
    ".graphql": "GraphQL",
    ".gql": "GraphQL",
    ".proto": "Protocol Buffers",
    ".rs": "Rust",
    ".go": "Go",
    ".java": "Java",
    ".kt": "Kotlin",
    ".kts": "Kotlin",
    ".c": "C",
    ".h": "C",
    ".cpp": "C++",
    ".hpp": "C++",
    ".cc": "C++",
    ".cxx": "C++",
    ".cs": "C#",
    ".rb": "Ruby",
    ".php": "PHP",
    ".swift": "Swift",
    ".scala": "Scala",
    ".r": "R",
    ".R": "R",
    ".jl": "Julia",
    ".lua": "Lua",
    ".pl": "Perl",
    ".pm": "Perl",
    ".vim": "Vim script",
    ".el": "Emacs Lisp",
    ".clj": "Clojure",
    ".cljs": "Clojure",
    ".ex": "Elixir",
    ".exs": "Elixir",
    ".erl": "Erlang",
    ".hrl": "Erlang",
    ".hs": "Haskell",
    ".ml": "OCaml",
    ".mli": "OCaml",
    ".fs": "F#",
    ".fsx": "F#",
    ".dart": "Dart",
    ".vue": "Vue",
    ".svelte": "Svelte",
    ".astro": "Astro",
    ".cmake": "CMake",
    ".gradle": "Gradle",
    ".nix": "Nix",
    ".tf": "Terraform",
    ".tfvars": "Terraform",
    ".hcl": "HCL",
    ".wat": "WebAssembly",
    ".ini": "INI",
    ".cfg": "Config",
    ".conf": "Config",
    ".properties": "Properties",
    ".mod": "Go",
    ".sum": "Go",
    ".csv": "CSV",
    ".tsv": "TSV",
    ".txt": "Plain text",
    ".log": "Log",
    ".lock": "Lockfile",
}

# Excluded when picking the headline "primary language" (still counted in full stats).
PRIMARY_LANGUAGE_EXCLUDE = frozenset(
    {
        "Lockfile",
        "Plain text",
        "Log",
        "Git ignore",
        "Git attributes",
        "Environment",
        "EditorConfig",
        "CSV",
        "TSV",
        "JSON",
        "YAML",
        "TOML",
        "INI",
        "Config",
        "Properties",
    }
)

LANGUAGE_BY_FILENAME: dict[str, str] = {
    "dockerfile": "Docker",
    "makefile": "Makefile",
    "cmakelists.txt": "CMake",
    "jenkinsfile": "Groovy",
    "vagrantfile": "Ruby",
    "gemfile": "Ruby",
    "rakefile": "Ruby",
    "procfile": "Procfile",
    ".gitignore": "Git ignore",
    ".gitattributes": "Git attributes",
    ".editorconfig": "EditorConfig",
    ".env": "Environment",
    ".env.example": "Environment",
}


# ---------------------------------------------------------------------------
# Data models
# ---------------------------------------------------------------------------


@dataclass(slots=True)
class ExportConfig:
    source: Path
    export_dir: Path
    respect_gitignore: bool
    max_file_bytes: int | None
    follow_symlinks: bool
    ignore_file: Path
    extra_skip_globs: frozenset[str]
    encoding: str
    encoding_errors: Literal["strict", "replace", "ignore"]
    path_ignore: PathIgnoreMatcher | None = field(default=None, repr=False)

    @property
    def context_path(self) -> Path:
        return self.export_dir / "context.txt"

    @property
    def assets_dir(self) -> Path:
        return self.export_dir / "assets"

    @property
    def stats_json_path(self) -> Path:
        return self.export_dir / "statistics.json"

    @property
    def stats_txt_path(self) -> Path:
        return self.export_dir / "statistics.txt"


@dataclass(slots=True)
class FileRecord:
    rel_path: Path
    abs_path: Path
    size: int
    kind: FileKind
    mime: str | None = None
    language: str | None = None
    lines: int = 0
    tokens: int = 0
    asset_rel: Path | None = None
    sha256: str | None = None
    skip_reason: str | None = None
    context_start_line: int | None = None
    context_end_line: int | None = None


@dataclass(slots=True)
class IndexEntry:
    path: str
    start_line: int
    end_line: int
    kind: FileKind
    language: str | None = None
    mime: str | None = None
    source_lines: int = 0
    tokens: int = 0
    asset: str | None = None


@dataclass
class LanguageStats:
    language: str
    files: int = 0
    lines: int = 0
    tokens: int = 0
    bytes: int = 0


@dataclass
class ExportStats:
    scanned: int = 0
    exported_text: int = 0
    exported_binary: int = 0
    skipped: int = 0
    total_text_bytes: int = 0
    total_binary_bytes: int = 0
    total_lines: int = 0
    total_tokens: int = 0
    primary_language: str | None = None
    token_counter: str = "estimate"
    kinds: Counter[str] = field(default_factory=Counter)
    languages: dict[str, LanguageStats] = field(default_factory=dict)


# ---------------------------------------------------------------------------
# Ignore handling (gitignore-style patterns, no external deps)
# ---------------------------------------------------------------------------


@dataclass(slots=True)
class IgnoreRule:
    pattern: str
    negated: bool
    directory_only: bool
    anchored: bool

    def matches(self, rel_posix: str, is_dir: bool) -> bool:
        if self.directory_only and not is_dir:
            return False

        path = rel_posix
        name = Path(rel_posix).name

        if self.anchored:
            candidates = (path,)
        else:
            candidates = (path, name)
            if "/" in path:
                candidates = (*candidates, f"**/{name}", f"**/{path}")

        for candidate in candidates:
            if fnmatch.fnmatch(candidate, self.pattern) or fnmatch.fnmatchcase(
                candidate, self.pattern
            ):
                return True
        return False


def parse_ignore_line(line: str) -> IgnoreRule | None:
    line = line.strip()
    if not line or line.startswith("#"):
        return None

    negated = line.startswith("!")
    if negated:
        line = line[1:]

    directory_only = line.endswith("/")
    if directory_only:
        line = line.rstrip("/")

    anchored = not line.startswith("/") and ("/" in line or line.startswith("*"))
    if line.startswith("/"):
        line = line[1:]
        anchored = True

    return IgnoreRule(
        pattern=line,
        negated=negated,
        directory_only=directory_only,
        anchored=anchored,
    )


class PathIgnoreMatcher:
    """Flat gitignore-style matcher loaded from ``.contextifyignore`` (etc.)."""

    def __init__(self, root: Path) -> None:
        self.root = root.resolve()
        self.rules: list[IgnoreRule] = []

    def load_file(self, path: Path) -> None:
        try:
            lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
        except OSError as exc:
            raise SystemExit(f"Cannot read ignore file {path}: {exc}") from exc
        for raw in lines:
            rule = parse_ignore_line(raw)
            if rule is not None:
                self.rules.append(rule)

    def add_pattern(self, pattern: str) -> None:
        rule = parse_ignore_line(pattern)
        if rule is not None:
            self.rules.append(rule)

    def is_ignored(self, path: Path, is_dir: bool) -> bool:
        path = path.resolve()
        try:
            rel = path.relative_to(self.root)
        except ValueError:
            return True

        rel_posix = rel.as_posix()
        if rel_posix == ".":
            return False

        ignored = False
        for rule in self.rules:
            if rule.matches(rel_posix, is_dir):
                ignored = not rule.negated
        return ignored


class GitIgnoreMatcher:
    """Merge rules from nested .gitignore files (last match wins)."""

    def __init__(self, root: Path) -> None:
        self.root = root.resolve()
        self._rules_by_dir: dict[Path, list[IgnoreRule]] = {}

    def _load_dir(self, directory: Path) -> None:
        directory = directory.resolve()
        if directory in self._rules_by_dir:
            return

        rules: list[IgnoreRule] = []
        gitignore = directory / ".gitignore"
        if gitignore.is_file():
            try:
                for raw in gitignore.read_text(encoding="utf-8", errors="replace").splitlines():
                    rule = parse_ignore_line(raw)
                    if rule is not None:
                        rules.append(rule)
            except OSError:
                pass

        parent = directory.parent
        if parent != directory and (self.root in parent.parents or parent == self.root):
            self._load_dir(parent)
            rules = [*self._rules_by_dir[parent], *rules]

        self._rules_by_dir[directory] = rules

    def is_ignored(self, path: Path, is_dir: bool) -> bool:
        path = path.resolve()
        try:
            rel = path.relative_to(self.root)
        except ValueError:
            return True

        rel_posix = rel.as_posix()
        if rel_posix == ".":
            return False

        directory = path if is_dir else path.parent
        self._load_dir(directory)
        rules = self._rules_by_dir.get(directory.resolve(), [])

        ignored = False
        for rule in rules:
            if rule.matches(rel_posix, is_dir):
                ignored = not rule.negated
        return ignored


def locate_ignore_file(source: Path, explicit: Path | None) -> Path:
    if explicit is not None:
        path = explicit.expanduser().resolve()
        if not path.is_file():
            raise SystemExit(f"Ignore file not found: {path}")
        return path

    for name in IGNORE_FILENAMES:
        candidate = source / name
        if candidate.is_file():
            return candidate

    bundled = bundled_ignore_file()
    if bundled.is_file():
        return bundled

    raise SystemExit(
        "No ignore file found. Add .contextifyignore to the repo root "
        f"or pass --ignore-file (bundled template: {bundled})"
    )


def export_dir_ignore_patterns(source: Path, export_dir: Path) -> list[str]:
    """Patterns that exclude the active export directory from the walk."""
    try:
        rel = export_dir.resolve().relative_to(source.resolve())
    except ValueError:
        return []

    posix = rel.as_posix()
    name = rel.name
    patterns = [posix, f"{posix}/**", f"{posix}/**/*"]
    if "/" not in posix:
        patterns.extend([name, f"{name}/", f"{name}/**"])
    return patterns


def build_path_ignore_matcher(config: ExportConfig) -> PathIgnoreMatcher:
    matcher = PathIgnoreMatcher(config.source)
    matcher.load_file(config.ignore_file)
    for pattern in export_dir_ignore_patterns(config.source, config.export_dir):
        matcher.add_pattern(pattern)
    for pattern in config.extra_skip_globs:
        matcher.add_pattern(pattern)
    return matcher


# ---------------------------------------------------------------------------
# Utilities
# ---------------------------------------------------------------------------


def parse_size(value: str) -> int:
    """Parse human-readable sizes like ``10M``, ``512K``, ``2G``."""
    match = re.fullmatch(r"(?i)(\d+(?:\.\d+)?)\s*([kmgt]?b?)?", value.strip())
    if not match:
        raise argparse.ArgumentTypeError(f"invalid size: {value!r}")

    number = float(match.group(1))
    unit = (match.group(2) or "b").lower().rstrip("b") or ""
    multipliers = {"": 1, "k": 1024, "m": 1024**2, "g": 1024**3, "t": 1024**4}
    if unit not in multipliers:
        raise argparse.ArgumentTypeError(f"unknown size unit in: {value!r}")
    return int(number * multipliers[unit])


def human_bytes(num: int) -> str:
    if num < 1024:
        return f"{num} B"
    for unit in ("KiB", "MiB", "GiB", "TiB"):
        num_f = num / 1024
        if num_f < 1024:
            return f"{num_f:.1f} {unit}"
        num = int(num_f)
    return f"{num} TiB"


def sha256_file(path: Path, chunk_size: int = 1 << 20) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while chunk := handle.read(chunk_size):
            digest.update(chunk)
    return digest.hexdigest()


def detect_mime(path: Path) -> str | None:
    mime, _ = mimetypes.guess_type(path.name)
    if mime:
        return mime
    if path.suffix.lower() in MEDIA_EXTENSIONS:
        return f"application/octet-stream ({path.suffix.lower()})"
    return None


def classify_file(path: Path, encoding: str) -> FileKind:
    ext = path.suffix.lower()
    if ext in MEDIA_EXTENSIONS:
        return "binary"

    # Extension hint is not decisive — sniff content.
    try:
        sample = path.read_bytes()[:8192]
    except OSError:
        return "skipped"

    if b"\x00" in sample:
        return "binary"

    if ext in TEXT_EXTENSIONS or ext == "":
        try:
            sample.decode(encoding)
            return "text"
        except UnicodeDecodeError:
            return "binary"

    # Heuristic: high ratio of printable ASCII / UTF-8
    try:
        sample.decode(encoding)
        text_chars = sum(32 <= b < 127 or b in (9, 10, 13) for b in sample)
        if sample and text_chars / len(sample) > 0.85:
            return "text"
    except UnicodeDecodeError:
        pass

    return "binary"


def detect_language(path: Path) -> str:
    name_key = path.name.lower()
    if name_key in LANGUAGE_BY_FILENAME:
        return LANGUAGE_BY_FILENAME[name_key]

    ext = path.suffix.lower()
    if ext in LANGUAGE_BY_EXTENSION:
        return LANGUAGE_BY_EXTENSION[ext]

    if ext == "" and path.name.isupper():
        return "Makefile"

    return "Other"


_tiktoken_encoder = None
_token_counter_name = "estimate/chars÷4"
_token_backend_ready = False


def _ensure_token_backend() -> None:
    global _tiktoken_encoder, _token_counter_name, _token_backend_ready
    if _token_backend_ready:
        return
    _token_backend_ready = True
    try:
        import tiktoken

        _tiktoken_encoder = tiktoken.get_encoding("cl100k_base")
        _token_counter_name = "tiktoken/cl100k_base"
    except (ImportError, ValueError, OSError):
        # ValueError/OSError: PyInstaller bundle without tiktoken encoding assets
        pass


def count_tokens(text: str) -> int:
    """Count tokens; uses tiktoken when installed, else chars/4 estimate."""
    if not text:
        return 0
    _ensure_token_backend()
    if _tiktoken_encoder is not None:
        return len(_tiktoken_encoder.encode(text, disallowed_special=()))
    return max(1, len(text) // 4)


def token_counter_name() -> str:
    _ensure_token_backend()
    return _token_counter_name


def count_lines(text: str) -> int:
    if not text:
        return 0
    return text.count("\n") + (1 if not text.endswith("\n") else 0)


def record_language(stats: ExportStats, record: FileRecord, content: str) -> None:
    record.language = detect_language(record.rel_path)
    record.lines = count_lines(content)
    record.tokens = count_tokens(content)

    stats.total_lines += record.lines
    stats.total_tokens += record.tokens

    bucket = stats.languages.setdefault(record.language, LanguageStats(language=record.language))
    bucket.files += 1
    bucket.lines += record.lines
    bucket.tokens += record.tokens
    bucket.bytes += record.size


def compute_primary_language(stats: ExportStats) -> str | None:
    if not stats.languages:
        return None

    code_langs = [
        lang for lang in stats.languages.values() if lang.language not in PRIMARY_LANGUAGE_EXCLUDE
    ]
    pool = code_langs or list(stats.languages.values())
    ranked = sorted(pool, key=lambda lang: (-lang.tokens, -lang.bytes, lang.language))
    stats.primary_language = ranked[0].language
    return stats.primary_language


def setup_logging(verbose: int) -> tuple[logging.Logger, Console | None]:
    level = logging.WARNING
    if verbose < 0:
        level = logging.ERROR
    elif verbose == 1:
        level = logging.INFO
    elif verbose >= 2:
        level = logging.DEBUG

    logger = logging.getLogger("contextify")
    logger.handlers.clear()
    logger.setLevel(level)
    logger.propagate = False

    console = Console(stderr=True) if _RICH else None

    if _RICH and console is not None:
        handler: logging.Handler = RichHandler(
            console=console,
            show_time=True,
            show_path=verbose >= 2,
            markup=True,
            rich_tracebacks=True,
        )
    else:
        handler = logging.StreamHandler(sys.stderr)
        handler.setFormatter(
            logging.Formatter(
                fmt="%(asctime)s | %(levelname)-8s | %(message)s",
                datefmt="%H:%M:%S",
            )
        )

    handler.setLevel(level)
    logger.addHandler(handler)
    return logger, console


# ---------------------------------------------------------------------------
# Discovery
# ---------------------------------------------------------------------------


def iter_repo_files(config: ExportConfig, logger: logging.Logger) -> Iterator[Path]:
    root = config.source.resolve()
    gitignore = GitIgnoreMatcher(root) if config.respect_gitignore else None
    export_ignore = config.path_ignore
    if export_ignore is None:
        raise RuntimeError(
            "path_ignore matcher not initialised — call build_path_ignore_matcher() first"
        )

    for dirpath, dirnames, filenames in os.walk(root, followlinks=config.follow_symlinks):
        current = Path(dirpath)

        kept: list[str] = []
        for name in sorted(dirnames):
            child = current / name
            if export_ignore.is_ignored(child, is_dir=True):
                logger.debug("skip dir (export ignore): %s", child.relative_to(root))
                continue
            if gitignore and gitignore.is_ignored(child, is_dir=True):
                logger.debug("skip dir (gitignore): %s", child.relative_to(root))
                continue
            kept.append(name)
        dirnames[:] = kept

        for name in sorted(filenames):
            path = current / name
            if export_ignore.is_ignored(path, is_dir=False):
                logger.debug("skip file (export ignore): %s", path.relative_to(root))
                continue
            if gitignore and gitignore.is_ignored(path, is_dir=False):
                logger.debug("skip file (gitignore): %s", path.relative_to(root))
                continue

            yield path


def build_file_records(
    config: ExportConfig,
    logger: logging.Logger,
    progress: Progress | None = None,
) -> list[FileRecord]:
    root = config.source.resolve()
    paths = list(iter_repo_files(config, logger))
    records: list[FileRecord] = []

    task_id = None
    if progress is not None:
        task_id = progress.add_task("Inspecting files", total=len(paths))

    for path in paths:
        rel = path.relative_to(root)
        try:
            size = path.stat().st_size
        except OSError as exc:
            records.append(
                FileRecord(
                    rel_path=rel,
                    abs_path=path,
                    size=0,
                    kind="skipped",
                    skip_reason=str(exc),
                )
            )
            if progress and task_id is not None:
                progress.advance(task_id)
            continue

        if config.max_file_bytes is not None and size > config.max_file_bytes:
            records.append(
                FileRecord(
                    rel_path=rel,
                    abs_path=path,
                    size=size,
                    kind="skipped",
                    skip_reason=f"exceeds max size ({human_bytes(config.max_file_bytes)})",
                )
            )
            if progress and task_id is not None:
                progress.advance(task_id)
            continue

        kind = classify_file(path, config.encoding)
        mime = detect_mime(path) if kind == "binary" else "text/plain"

        records.append(
            FileRecord(
                rel_path=rel,
                abs_path=path,
                size=size,
                kind=kind,
                mime=mime,
            )
        )
        if progress and task_id is not None:
            progress.advance(task_id)

    return sorted(records, key=lambda r: r.rel_path.as_posix().lower())


# ---------------------------------------------------------------------------
# Export
# ---------------------------------------------------------------------------


@dataclass
class _TreeNode:
    dirs: dict[str, _TreeNode] = field(default_factory=dict)
    files: list[str] = field(default_factory=list)


def _tree_insert(node: _TreeNode, parts: tuple[str, ...]) -> None:
    if not parts:
        return
    if len(parts) == 1:
        node.files.append(parts[0])
        return
    child = node.dirs.setdefault(parts[0], _TreeNode())
    _tree_insert(child, parts[1:])


def build_file_tree(rel_paths: list[Path], root_label: str) -> str:
    root = _TreeNode()
    for rel in rel_paths:
        _tree_insert(root, rel.parts)

    lines = [f"{root_label}/"]

    def walk(node: _TreeNode, prefix: str) -> None:
        ordered: list[tuple[str, _TreeNode | None]] = [
            (name, child)
            for name, child in sorted(node.dirs.items(), key=lambda item: item[0].lower())
        ]
        ordered.extend((name, None) for name in sorted(node.files, key=str.lower))

        for index, (name, child) in enumerate(ordered):
            is_last = index == len(ordered) - 1
            branch = "└── " if is_last else "├── "
            extension = "    " if is_last else "│   "
            if child is None:
                lines.append(f"{prefix}{branch}{name}")
            else:
                lines.append(f"{prefix}{branch}{name}/")
                walk(child, prefix + extension)

    walk(root, "")
    return "\n".join(lines) + "\n"


def format_file_index(entries: list[IndexEntry]) -> str:
    rows = ["path\tstart\tend\tkind\tlang\ttokens"]
    for entry in entries:
        lang = entry.language or entry.mime or ""
        tokens = entry.tokens if entry.tokens else ""
        rows.append(
            f"{entry.path}\t{entry.start_line}\t{entry.end_line}\t{entry.kind}\t{lang}\t{tokens}"
        )
    return "\n".join(rows) + "\n"


def format_file_header_line(record: FileRecord) -> str:
    path = record.rel_path.as_posix()
    if record.kind == "binary":
        asset = record.asset_rel.as_posix() if record.asset_rel else ""
        digest = record.sha256[:16] if record.sha256 else ""
        return f"=== {path} [binary asset={asset} sha={digest}] ==="
    meta: list[str] = []
    if record.language:
        meta.append(record.language)
    if record.lines:
        meta.append(f"{record.lines}L")
    if record.tokens:
        meta.append(f"{record.tokens}tok")
    suffix = f" [{', '.join(meta)}]" if meta else ""
    return f"=== {path}{suffix} ==="


class _ContextWriter:
    """Append to a buffer while tracking 1-based line numbers in the final file."""

    def __init__(self) -> None:
        self._buffer = io.StringIO()
        self.line = 1

    def write(self, text: str) -> int:
        start = self.line
        self._buffer.write(text)
        self.line += text.count("\n")
        if text and not text.endswith("\n"):
            self.line += 1
        return start

    def writeln(self, text: str = "") -> int:
        return self.write(text + "\n")

    def getvalue(self) -> str:
        return self._buffer.getvalue()


def write_raw_content(writer: _ContextWriter, content: str) -> None:
    if not content:
        return
    writer.write(content)
    if not content.endswith("\n"):
        writer.writeln()


def prepare_export_dir(config: ExportConfig) -> None:
    if config.export_dir.exists():
        shutil.rmtree(config.export_dir)
    config.export_dir.mkdir(parents=True, exist_ok=True)
    config.assets_dir.mkdir(parents=True, exist_ok=True)


def write_export_bundle(
    config: ExportConfig,
    records: Iterable[FileRecord],
    logger: logging.Logger,
    progress: Progress | None = None,
) -> ExportStats:
    stats = ExportStats(token_counter=token_counter_name())
    root = config.source.resolve()
    prepare_export_dir(config)

    record_list = list(records)
    exportable = [r for r in record_list if r.kind != "skipped"]
    task_id = None
    if progress is not None:
        task_id = progress.add_task("Writing export", total=len(exportable))

    generated_at = datetime.now(UTC).strftime("%Y-%m-%d %H:%M:%S UTC")
    contents = _ContextWriter()
    index_entries: list[IndexEntry] = []

    for record in record_list:
        stats.scanned += 1
        if record.kind == "skipped":
            stats.skipped += 1
            logger.warning("Skipped %s — %s", record.rel_path, record.skip_reason)
            if progress and task_id is not None:
                progress.advance(task_id)
            continue

        if record.kind == "text":
            try:
                content = record.abs_path.read_text(
                    encoding=config.encoding,
                    errors=config.encoding_errors,
                )
            except OSError as exc:
                stats.skipped += 1
                logger.error("Failed to read %s: %s", record.rel_path, exc)
                rel_start = contents.writeln(format_file_header_line(record))
                contents.writeln(f"[read error: {exc}]")
                rel_end = contents.line - 1
                index_entries.append(
                    IndexEntry(
                        path=record.rel_path.as_posix(),
                        start_line=rel_start,
                        end_line=rel_end,
                        kind=record.kind,
                        mime=record.mime,
                    )
                )
                if progress and task_id is not None:
                    progress.advance(task_id)
                continue

            record_language(stats, record, content)
            rel_start = contents.writeln(format_file_header_line(record))
            write_raw_content(contents, content)

            stats.exported_text += 1
            stats.total_text_bytes += record.size
            stats.kinds["text"] += 1
            logger.debug(
                "Inlined text: %s (%s, %s tokens)",
                record.rel_path,
                record.language,
                record.tokens,
            )

        else:  # binary
            dest = config.assets_dir / record.rel_path
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(record.abs_path, dest)
            record.sha256 = sha256_file(dest)
            record.asset_rel = Path("assets") / record.rel_path

            stats.exported_binary += 1
            stats.total_binary_bytes += record.size
            stats.kinds[record.mime or "binary"] += 1

            rel_start = contents.writeln(format_file_header_line(record))
            logger.debug("Copied asset: %s → %s", record.rel_path, record.asset_rel)

        rel_end = contents.line - 1

        index_entries.append(
            IndexEntry(
                path=record.rel_path.as_posix(),
                start_line=rel_start,
                end_line=rel_end,
                kind=record.kind,
                language=record.language,
                mime=record.mime,
                source_lines=record.lines,
                tokens=record.tokens,
                asset=record.asset_rel.as_posix() if record.asset_rel else None,
            )
        )

        if progress and task_id is not None:
            progress.advance(task_id)

    tree = build_file_tree([r.rel_path for r in exportable], root.name)
    contents_body = contents.getvalue()

    preamble = (
        f"# EXPORT source={root} generated={generated_at} encoding={config.encoding}\n"
        f"# {NAVIGATION_GUIDE}\n"
        f"{SECTION_BREAK} TREE {SECTION_BREAK}\n"
        f"{tree}"
        f"{SECTION_BREAK}\n"
    )

    index_intro = (
        f"{SECTION_BREAK} INDEX (path\\tstart\\tend\\tkind\\tlang\\ttokens) {SECTION_BREAK}\n"
    )
    contents_intro = f"{SECTION_BREAK} CONTENTS {SECTION_BREAK}\n"

    preamble_lines = count_lines(preamble)
    index_intro_lines = count_lines(index_intro)
    contents_intro_lines = count_lines(contents_intro)
    index_body_lines = count_lines(format_file_index(index_entries)) + 1  # trailing newline

    contents_base_line = (
        preamble_lines + index_intro_lines + index_body_lines + contents_intro_lines + 1
    )

    for entry in index_entries:
        entry.start_line += contents_base_line - 1
        entry.end_line += contents_base_line - 1

    for record in record_list:
        if record.kind == "skipped":
            continue
        for entry in index_entries:
            if entry.path == record.rel_path.as_posix():
                record.context_start_line = entry.start_line
                record.context_end_line = entry.end_line
                break

    final_text = (
        preamble + index_intro + format_file_index(index_entries) + contents_intro + contents_body
    )
    config.context_path.write_text(final_text, encoding="utf-8")

    compute_primary_language(stats)
    return stats


def language_share(stats: ExportStats, lang: LanguageStats) -> float:
    if stats.total_tokens <= 0:
        return 0.0
    return 100.0 * lang.tokens / stats.total_tokens


def write_statistics(
    config: ExportConfig,
    stats: ExportStats,
    elapsed_s: float,
    records: list[FileRecord],
) -> None:
    root = config.source.resolve()
    generated_at = datetime.now(UTC).isoformat()

    ranked_languages = sorted(
        stats.languages.values(),
        key=lambda lang: (-lang.tokens, -lang.bytes, lang.language),
    )

    payload = {
        "source": str(root),
        "export_dir": str(config.export_dir.resolve()),
        "generated_at": generated_at,
        "encoding": config.encoding,
        "token_counter": stats.token_counter,
        "elapsed_seconds": round(elapsed_s, 3),
        "summary": {
            "files_scanned": stats.scanned,
            "text_files": stats.exported_text,
            "binary_files": stats.exported_binary,
            "skipped_files": stats.skipped,
            "total_lines": stats.total_lines,
            "total_tokens": stats.total_tokens,
            "text_bytes": stats.total_text_bytes,
            "binary_bytes": stats.total_binary_bytes,
            "primary_language": stats.primary_language,
        },
        "languages": [
            {
                "language": lang.language,
                "files": lang.files,
                "lines": lang.lines,
                "tokens": lang.tokens,
                "bytes": lang.bytes,
                "token_share_pct": round(language_share(stats, lang), 2),
            }
            for lang in ranked_languages
        ],
        "binary_mime_types": [
            {"mime": mime, "count": count}
            for mime, count in stats.kinds.most_common()
            if mime != "text"
        ],
        "file_index": [
            {
                "path": entry.path,
                "context_start_line": entry.start_line,
                "context_end_line": entry.end_line,
                "kind": entry.kind,
                "language": entry.language,
                "mime": entry.mime,
                "source_lines": entry.source_lines,
                "tokens": entry.tokens,
                "asset": entry.asset,
            }
            for entry in sorted(
                (
                    IndexEntry(
                        path=r.rel_path.as_posix(),
                        start_line=r.context_start_line or 0,
                        end_line=r.context_end_line or 0,
                        kind=r.kind,
                        language=r.language,
                        mime=r.mime,
                        source_lines=r.lines,
                        tokens=r.tokens,
                        asset=r.asset_rel.as_posix() if r.asset_rel else None,
                    )
                    for r in records
                    if r.kind != "skipped" and r.context_start_line
                ),
                key=lambda item: item.start_line,
            )
        ],
        "files": [
            {
                "path": record.rel_path.as_posix(),
                "kind": record.kind,
                "size": record.size,
                "language": record.language,
                "lines": record.lines,
                "tokens": record.tokens,
                "mime": record.mime,
                "asset": record.asset_rel.as_posix() if record.asset_rel else None,
                "sha256": record.sha256,
                "context_start_line": record.context_start_line,
                "context_end_line": record.context_end_line,
                "skipped": record.skip_reason,
            }
            for record in records
        ],
    }

    config.stats_json_path.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )

    lines = [
        SEPARATOR_MAJOR,
        "REPOSITORY STATISTICS",
        SEPARATOR_MAJOR,
        "",
        f"Source           : {root}",
        f"Export directory : {config.export_dir.resolve()}",
        f"Generated        : {generated_at}",
        f"Token counter    : {stats.token_counter}",
        f"Elapsed          : {elapsed_s:.2f}s",
        "",
        "── Summary " + "─" * 66,
        f"  Files scanned    : {stats.scanned}",
        f"  Text files       : {stats.exported_text}",
        f"  Binary assets    : {stats.exported_binary}",
        f"  Skipped          : {stats.skipped}",
        f"  Total lines      : {stats.total_lines:,}",
        f"  Total tokens     : {stats.total_tokens:,}",
        f"  Text volume      : {human_bytes(stats.total_text_bytes)}",
        f"  Binary volume    : {human_bytes(stats.total_binary_bytes)}",
        f"  Primary language : {stats.primary_language or 'n/a'}",
        "",
        "── Languages (by token share) " + "─" * 48,
    ]

    for lang in ranked_languages:
        share = language_share(stats, lang)
        lines.append(
            f"  {lang.language:<22}  {lang.files:>4} files  "
            f"{lang.tokens:>10,} tokens  {share:>5.1f}%  {human_bytes(lang.bytes):>10}"
        )

    if stats.kinds:
        lines.extend(["", "── Binary MIME types " + "─" * 58])
        for mime, count in stats.kinds.most_common():
            if mime == "text":
                continue
            lines.append(f"  {mime:<40}  {count:>4}")

    lines.extend(["", SEPARATOR_MAJOR, ""])
    config.stats_txt_path.write_text("\n".join(lines), encoding="utf-8")


def render_summary(
    stats: ExportStats,
    config: ExportConfig,
    elapsed_s: float,
    console: Console | None,
    logger: logging.Logger,
) -> None:
    if _RICH and console is not None:
        table = Table(title="Export complete", show_header=True, header_style="bold cyan")
        table.add_column("Metric", style="bold")
        table.add_column("Value", justify="right")

        table.add_row("Text files inlined", str(stats.exported_text))
        table.add_row("Binary assets copied", str(stats.exported_binary))
        table.add_row("Skipped", str(stats.skipped))
        table.add_row("Total lines", f"{stats.total_lines:,}")
        table.add_row("Total tokens", f"{stats.total_tokens:,}")
        table.add_row("Primary language", stats.primary_language or "n/a")
        table.add_row("Token counter", stats.token_counter)
        table.add_row("Text volume", human_bytes(stats.total_text_bytes))
        table.add_row("Binary volume", human_bytes(stats.total_binary_bytes))
        table.add_row("Elapsed", f"{elapsed_s:.2f}s")
        table.add_row("Export dir", str(config.export_dir.resolve()))

        console.print()
        console.print(table)

        if stats.languages:
            langs = Table(title="Languages", show_header=True, header_style="bold green")
            langs.add_column("Language")
            langs.add_column("Files", justify="right")
            langs.add_column("Tokens", justify="right")
            langs.add_column("Share", justify="right")
            for lang in sorted(stats.languages.values(), key=lambda item: -item.tokens)[:8]:
                langs.add_row(
                    lang.language,
                    str(lang.files),
                    f"{lang.tokens:,}",
                    f"{language_share(stats, lang):.1f}%",
                )
            console.print(langs)

        if stats.kinds:
            kinds = Table(
                title="Binary MIME breakdown", show_header=True, header_style="bold magenta"
            )
            kinds.add_column("Type")
            kinds.add_column("Count", justify="right")
            for mime, count in stats.kinds.most_common(8):
                if mime == "text":
                    continue
                kinds.add_row(mime, str(count))
            if len([k for k in stats.kinds if k != "text"]) > 0:
                console.print(kinds)
    else:
        logger.info("Text files: %s", stats.exported_text)
        logger.info("Binary assets: %s", stats.exported_binary)
        logger.info("Tokens: %s (%s)", f"{stats.total_tokens:,}", stats.token_counter)
        logger.info("Primary language: %s", stats.primary_language)
        logger.info("Wrote %s", config.export_dir.resolve())


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Export a repository into a folder: context.txt, assets/, and statistics.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
        epilog=(
            "Release binaries are self-contained (no Python install required). "
            "From-source installs: pip install 'contextify[rich]' for progress UI."
        ),
    )
    parser.add_argument(
        "source",
        type=Path,
        help="Repository root to export",
    )
    parser.add_argument(
        "-o",
        "--output",
        type=Path,
        default=None,
        help="Output directory (default: ./context_export/ in the current working directory)",
    )
    parser.add_argument(
        "--no-gitignore",
        action="store_true",
        help="Do not honour .gitignore rules",
    )
    parser.add_argument(
        "--max-size",
        type=parse_size,
        default=None,
        metavar="SIZE",
        help="Skip files larger than SIZE (e.g. 5M, 100K, 1G)",
    )
    parser.add_argument(
        "--follow-symlinks",
        action="store_true",
        help="Follow symbolic links while walking the tree",
    )
    parser.add_argument(
        "--encoding",
        default="utf-8",
        help="Text encoding used when reading source files",
    )
    parser.add_argument(
        "--encoding-errors",
        choices=("strict", "replace", "ignore"),
        default="replace",
        help="How to handle text decoding errors",
    )
    parser.add_argument(
        "--ignore-file",
        type=Path,
        default=None,
        help="Export ignore file (default: .contextifyignore in repo, else bundled template)",
    )
    parser.add_argument(
        "--skip-glob",
        action="append",
        default=[],
        metavar="PATTERN",
        help="Extra gitignore-style pattern (repeatable; prefer editing .contextifyignore)",
    )
    parser.add_argument(
        "-v",
        "--verbose",
        action="count",
        default=0,
        help="Increase logging verbosity (-v info, -vv debug)",
    )
    parser.add_argument(
        "-q",
        "--quiet",
        action="store_true",
        help="Only show errors (overrides -v)",
    )
    return parser


def resolve_paths(args: argparse.Namespace) -> ExportConfig:
    source = args.source.expanduser().resolve()
    if not source.is_dir():
        raise SystemExit(f"Source is not a directory: {source}")

    if args.output is None:
        export_dir = Path.cwd() / DEFAULT_EXPORT_DIRNAME
    else:
        export_dir = args.output.expanduser().resolve()

    ignore_file = locate_ignore_file(source, args.ignore_file)

    return ExportConfig(
        source=source,
        export_dir=export_dir,
        respect_gitignore=not args.no_gitignore,
        max_file_bytes=args.max_size,
        follow_symlinks=args.follow_symlinks,
        ignore_file=ignore_file,
        extra_skip_globs=frozenset(args.skip_glob),
        encoding=args.encoding,
        encoding_errors=args.encoding_errors,
    )


def run_export(
    config: ExportConfig, logger: logging.Logger, console: Console | None
) -> ExportStats:
    started = time.perf_counter()
    records: list[FileRecord]

    if _RICH and console is not None:
        progress_columns = [
            SpinnerColumn(),
            TextColumn("[bold blue]{task.description}"),
            BarColumn(bar_width=40),
            TaskProgressColumn(),
            MofNCompleteColumn(),
            TimeElapsedColumn(),
            TimeRemainingColumn(),
        ]
        with Progress(*progress_columns, console=console, transient=False) as progress:
            records = build_file_records(config, logger, progress)
            stats = write_export_bundle(config, records, logger, progress)
    else:
        logger.info("Scanning %s ...", config.source)
        records = build_file_records(config, logger, None)
        logger.info("Found %s files — writing export ...", len(records))
        stats = write_export_bundle(config, records, logger, None)

    elapsed = time.perf_counter() - started
    write_statistics(config, stats, elapsed, records)
    render_summary(stats, config, elapsed, console, logger)
    return stats


def main(argv: list[str] | None = None) -> int:
    parser = build_arg_parser()
    args = parser.parse_args(argv)

    if args.quiet:
        args.verbose = -1

    logger, console = setup_logging(0 if args.quiet else args.verbose)

    if not _RICH and not is_frozen_binary() and not args.quiet:
        logger.warning(
            "Progress UI unavailable — use the release binary or: pip install 'contextify[rich]'"
        )

    config = resolve_paths(args)
    config.path_ignore = build_path_ignore_matcher(config)

    if console is not None:
        title = Text("contextify", style="bold green")
        console.print(title, justify="center")
        console.print(f"[dim]Source[/dim]      {config.source}")
        console.print(f"[dim]Export dir[/dim]  {config.export_dir}")
        console.print(f"[dim]Ignore file[/dim] {config.ignore_file}")
        console.print()

    try:
        stats = run_export(config, logger, console)
    except KeyboardInterrupt:
        if console:
            console.print("\n[red]Interrupted[/red]")
        else:
            print("\nInterrupted.", file=sys.stderr)
        return 130

    if stats.exported_text == 0 and stats.exported_binary == 0:
        logger.error("Nothing exported — check paths, gitignore, or filters.")
        return 1
    return 0
