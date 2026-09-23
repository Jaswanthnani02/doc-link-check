#!/usr/bin/env python3
"""Verify that every relative link in a project's Markdown resolves.

Checks links between files, not links to the internet. Nothing is fetched, so
it needs no network, no credentials and no configuration, and it is fast
enough to run on every push.

Exits 0 when every relative link resolves, 1 otherwise, listing each broken
link with the file and line it appears on.
"""
from __future__ import annotations

import argparse
import os
import re
import subprocess
import sys
from pathlib import Path

__version__ = "1.0.0"

# [text](target) and [text](target "title"), excluding image-only syntax is
# unnecessary: a broken image path is a broken link too.
LINK = re.compile(r"\[[^\]]*\]\(\s*<?([^)>\s]+)>?(?:\s+\"[^\"]*\")?\s*\)")

# Reference-style definitions: [label]: target
REF_DEF = re.compile(r"^\s{0,3}\[[^\]]+\]:\s*<?([^>\s]+)>?", re.MULTILINE)

EXTERNAL_PREFIXES = ("http://", "https://", "mailto:", "tel:", "ftp://", "//")

# ``` or ~~~ fence, with an optional info string
FENCE = re.compile(r"^\s{0,3}(`{3,}|~{3,})")

# An inline code span: one or more backticks, content, matching run of backticks
INLINE_CODE = re.compile(r"(?P<ticks>`+)(?:.*?)(?P=ticks)")

DEFAULT_IGNORES = [
    ".git", ".venv", "venv", "node_modules", "__pycache__",
    ".tox", ".mypy_cache", ".pytest_cache", "vendor", "dist", "build",
]


def _git_tracked_markdown(root: Path) -> list[Path] | None:
    """Prefer git so ignored and untracked files are skipped for free.

    Returns None when this is not a git checkout or git is unavailable, and
    the caller falls back to walking the filesystem.
    """
    try:
        out = subprocess.run(
            ["git", "-C", str(root), "ls-files", "-z", "*.md", "*.markdown"],
            capture_output=True, check=True, timeout=30,
        ).stdout
    except (subprocess.CalledProcessError, FileNotFoundError, OSError, subprocess.TimeoutExpired):
        return None
    return [root / p.decode("utf-8") for p in out.split(b"\0") if p]


def _walk_markdown(root: Path, ignores: set[str]) -> list[Path]:
    found = []
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in ignores]
        for name in filenames:
            if name.lower().endswith((".md", ".markdown")):
                found.append(Path(dirpath) / name)
    return found


def collect_markdown(root: Path, ignores: set[str], use_git: bool) -> list[Path]:
    files = _git_tracked_markdown(root) if use_git else None
    if files is None:
        files = _walk_markdown(root, ignores)
    return sorted(
        f for f in files
        if f.exists() and not any(part in ignores for part in f.relative_to(root).parts)
    )


def strip_code(lines: list[str]) -> list[str]:
    """Blank out fenced code blocks and inline code spans.

    Link syntax inside code is documentation *about* links, not a link. A
    README that shows `[text](target)` as an example must not be reported as
    having a broken link to a file called "target" — which is exactly what
    this tool did to its own README before this existed.

    Lines are replaced rather than removed so reported line numbers stay
    correct, and inline spans become spaces of equal length for the same
    reason.
    """
    out: list[str] = []
    fence: str | None = None

    for line in lines:
        m = FENCE.match(line)
        if fence is None and m:
            fence = m.group(1)[0] * 3
            out.append("")
            continue
        if fence is not None:
            # Only a fence of the same character closes the block
            if m and m.group(1)[0] * 3 == fence:
                fence = None
            out.append("")
            continue
        out.append(INLINE_CODE.sub(lambda mm: " " * len(mm.group(0)), line))

    return out


def _slugify(heading: str) -> str:
    """Approximate GitHub's heading-to-anchor rule.

    Lowercase, strip anything that is not a word character, space or hyphen,
    then turn each remaining whitespace character into a hyphen.

    Note the last step is per-character, not per-run. GitHub does not collapse
    runs, so "## CI / CD" anchors as "#ci--cd": removing the slash leaves two
    spaces, and each becomes its own hyphen. Collapsing here would silently
    pass a link that is actually broken on GitHub.

    Deliberately not exhaustive — emoji and some Unicode cases differ — which
    is why anchor checking is opt-in rather than on by default.
    """
    text = heading.strip().lstrip("#").strip()
    text = re.sub(r"[^\w\s-]", "", text, flags=re.UNICODE).strip().lower()
    return re.sub(r"\s", "-", text)


def _anchors_in(path: Path) -> set[str]:
    try:
        text = path.read_text(encoding="utf-8")
    except (UnicodeDecodeError, OSError):
        return set()
    # A '#' inside a fenced block is a shell comment, not a heading.
    text = "\n".join(strip_code(text.splitlines()))
    anchors = {_slugify(m) for m in re.findall(r"^\s{0,3}#{1,6}\s+(.+)$", text, re.MULTILINE)}
    # Explicit HTML anchors, e.g. <a id="x"> or <a name="x">
    anchors |= set(re.findall(r"<a\s+(?:id|name)=[\"']([^\"']+)[\"']", text))
    return anchors


def check(root: Path, ignores: set[str], use_git: bool, check_anchors: bool):
    files = collect_markdown(root, ignores, use_git)
    broken: list[tuple[str, int, str, str]] = []
    checked = 0
    anchor_cache: dict[Path, set[str]] = {}

    for path in files:
        rel = path.relative_to(root).as_posix()
        try:
            lines = path.read_text(encoding="utf-8").splitlines()
        except (UnicodeDecodeError, OSError):
            continue
        lines = strip_code(lines)

        for lineno, line in enumerate(lines, start=1):
            targets = LINK.findall(line) + REF_DEF.findall(line)
            for target in targets:
                if target.startswith(EXTERNAL_PREFIXES):
                    continue
                bare, _, anchor = target.partition("#")

                if not bare:
                    # Same-file anchor, e.g. (#section)
                    if check_anchors and anchor:
                        checked += 1
                        if anchor not in anchor_cache.setdefault(path, _anchors_in(path)):
                            broken.append((rel, lineno, target, "no such heading in this file"))
                    continue

                checked += 1
                resolved = (path.parent / bare).resolve()
                if not resolved.exists():
                    broken.append((rel, lineno, target, "file does not exist"))
                    continue

                if check_anchors and anchor and resolved.is_file() and resolved.suffix.lower() in (".md", ".markdown"):
                    if anchor.lower().startswith("l") and anchor[1:].isdigit():
                        continue  # #L42 line references are a GitHub UI feature, not a heading
                    if anchor not in anchor_cache.setdefault(resolved, _anchors_in(resolved)):
                        broken.append((rel, lineno, target, "file exists but has no such heading"))

    return files, checked, broken


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="doc-link-check",
        description="Verify that every relative link in a project's Markdown resolves.",
    )
    parser.add_argument("root", nargs="?", default=".", help="project root (default: current directory)")
    parser.add_argument("--ignore", action="append", default=[], metavar="DIR",
                        help="directory name to skip; repeatable, adds to the defaults")
    parser.add_argument("--no-git", action="store_true",
                        help="walk the filesystem instead of asking git which files are tracked")
    parser.add_argument("--check-anchors", action="store_true",
                        help="also verify that #fragments match a heading in the target file")
    parser.add_argument("--quiet", "-q", action="store_true", help="print nothing when everything resolves")
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    args = parser.parse_args(argv)

    root = Path(args.root).resolve()
    if not root.is_dir():
        print(f"error: {root} is not a directory", file=sys.stderr)
        return 2

    ignores = set(DEFAULT_IGNORES) | set(args.ignore)
    files, checked, broken = check(root, ignores, not args.no_git, args.check_anchors)

    if not files:
        print(f"no Markdown files found under {root}", file=sys.stderr)
        return 0

    if broken:
        print(f"{len(broken)} broken relative link(s) out of {checked} checked:\n", file=sys.stderr)
        for rel, lineno, target, why in broken:
            print(f"  {rel}:{lineno}  ->  {target}", file=sys.stderr)
            print(f"      {why}", file=sys.stderr)
        print("\nIf you moved a file, update every reference to it.", file=sys.stderr)
        return 1

    if not args.quiet:
        print(f"OK: {checked} relative links resolve across {len(files)} Markdown files.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
