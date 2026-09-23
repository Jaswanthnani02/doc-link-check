# doc-link-check

Verify that every relative link in your Markdown resolves. One file, no dependencies, no network.

```console
$ doc_link_check.py
OK: 88 relative links resolve across 74 Markdown files.
```

```console
$ doc_link_check.py
1 broken relative link(s) out of 89 checked:

  ARCHITECTURE.md:60  ->  runbooks/setup.md#tuning
      file does not exist

If you moved a file, update every reference to it.
```

Exit code is 0 when everything resolves and 1 when it does not, so it works as a CI gate.

## The problem it solves

Documentation links break silently. Nobody notices until someone follows one.

The failure mode that motivated this tool: a repository reorganised its `docs/` directory, moving about fifty files. Roughly thirty cross-references needed repairing, and a dozen of them were not in Markdown at all — they were paths cited in source comments, which no link checker would have caught and no test would have failed on.

The moves were the easy part. The part worth automating is everything that pointed at them.

A week later a second change landed that added a link to a file which had since moved to the repository root. Git carried the edit across the rename correctly and produced no conflict, so the link was quietly wrong. This check caught it in six seconds.

## Why relative links only

External URLs are a different problem with different tradeoffs. Fetching them needs network access, tolerates flakiness badly, gets rate-limited, and produces false failures when a site is briefly down — so teams end up allowlisting, retrying, and eventually ignoring the results.

Relative links are deterministic. A file either exists or it does not. That makes this check fast, hermetic, and trustworthy enough that a failure always means something is genuinely wrong. Run it on every push and act on every failure.

If you also want external link checking, use a dedicated tool for it on a nightly schedule, not on the critical path.

## Install

There is nothing to install. Copy `doc_link_check.py` into your repository and run it with Python 3.9 or newer.

```bash
curl -O https://raw.githubusercontent.com/<you>/doc-link-check/main/doc_link_check.py
python doc_link_check.py
```

Keeping it as a single vendored file is deliberate: a documentation check should not add a dependency, a lockfile entry, or a supply-chain surface.

## Usage

```console
$ python doc_link_check.py --help
usage: doc-link-check [-h] [--ignore DIR] [--no-git] [--check-anchors] [--quiet] [root]
```

| Option | Effect |
|---|---|
| `root` | Project root. Defaults to the current directory. |
| `--ignore DIR` | Skip a directory by name. Repeatable, and adds to the defaults. |
| `--no-git` | Walk the filesystem instead of asking git which files are tracked. |
| `--check-anchors` | Also verify that `#fragments` match a heading in the target file. |
| `--quiet` | Print nothing on success. Useful in pre-commit hooks. |

By default the tool asks `git ls-files` which Markdown is tracked, so ignored and untracked files are skipped for free. It falls back to walking the filesystem when git is unavailable or the directory is not a checkout.

Skipped by default: `.git`, `.venv`, `venv`, `node_modules`, `__pycache__`, `.tox`, `.mypy_cache`, `.pytest_cache`, `vendor`, `dist`, `build`.

## What it checks

Inline links `[text](target)`, angle-bracket targets `[text](<target>)`, titled links `[text](target "title")`, reference definitions `[label]: target`, and images `![alt](target)` — a broken image path is a broken link.

Skipped as external: `http://`, `https://`, `mailto:`, `tel:`, `ftp://`, and protocol-relative `//`.

### Anchors

Off by default, because heading-to-anchor conversion has edge cases — emoji and some Unicode headings do not round-trip predictably — and a checker that reports false failures is a checker people learn to ignore.

With `--check-anchors`, fragments are matched against headings in the target file and against explicit `<a id="...">` anchors. GitHub-style line references such as `#L42` are recognised and skipped, since they are a UI feature rather than a heading.

The slug rule matches GitHub's, including the part people get wrong: whitespace runs are **not** collapsed. `## CI / CD` anchors as `#ci--cd`, because removing the slash leaves two spaces and each becomes its own hyphen.

## In CI

```yaml
name: Docs link check

on:
  pull_request:
    paths: ["**/*.md"]
  push:
    branches: [main]
    paths: ["**/*.md"]

permissions:
  contents: read

jobs:
  links:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.11"
      - run: python doc_link_check.py
```

Worth making this its own workflow rather than a job inside your main CI. Widening an existing workflow's path filters to cover `**/*.md` means every documentation change runs your full test suite, and in repositories where those filters also drive deployment, that is a change you want to make deliberately rather than as a side effect.

### pre-commit

```yaml
- repo: local
  hooks:
    - id: doc-link-check
      name: doc-link-check
      entry: python doc_link_check.py --quiet
      language: system
      pass_filenames: false
      files: \.md$
```

## Development

```bash
python -m pytest tests/ -q
```

30 tests, no dependencies beyond `pytest`. Each builds a throwaway directory tree, so nothing depends on the repository the tests happen to live in.

## Licence

MIT. See [LICENSE](LICENSE).
