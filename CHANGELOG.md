# Changelog

All notable changes to this project are documented here.

The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.0.0] - 2026-09-23

First release.

### Added

- Relative link resolution across a project's Markdown, reported with file and
  line number, exiting non-zero when any link is broken.
- Support for inline links, angle-bracket targets, titled links,
  reference-style definitions and images.
- Git-aware file discovery via `git ls-files`, so ignored and untracked files
  are skipped, with a filesystem walk as fallback when git is unavailable or
  the directory is not a checkout.
- `--check-anchors`, verifying that `#fragments` match a heading or an explicit
  `<a id="...">` in the target file. Opt-in, because heading-to-anchor
  conversion has edge cases and a checker that reports false failures is one
  people learn to ignore.
- `--ignore`, `--no-git` and `--quiet` flags, and a default ignore list
  covering the usual vendored and build directories.
- 38 tests, each building a throwaway directory tree so none depends on the
  repository they live in. CI runs them on Python 3.9, 3.11 and 3.13.

### Notes on two behaviours that are easy to get wrong

**Whitespace runs in anchors are not collapsed.** GitHub removes punctuation
first and then converts each remaining space to a hyphen, so `## CI / CD`
anchors as `#ci--cd`, not `#ci-cd`. Collapsing would silently pass a link that
is actually broken.

**Code is excluded from scanning.** Link syntax inside a fenced block or a
backtick span is documentation *about* links, not a link. This was found by
running the tool against its own README, which reported four broken links to a
file called `target`.

[1.0.0]: https://github.com/Jaswanthnani02/doc-link-check/releases/tag/v1.0.0
