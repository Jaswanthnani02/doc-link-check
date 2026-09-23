# Contributing

## Running the tests

```bash
pip install pytest
python -m pytest tests/ -q
```

No other dependencies. The tool itself uses only the standard library, and that
is a constraint worth keeping — a documentation check should not add a
dependency, a lockfile entry, or a supply-chain surface to the project it
guards.

Before opening a pull request, also run the tool against this repository:

```bash
python doc_link_check.py --check-anchors
```

CI does both, on Python 3.9, 3.11 and 3.13.

## Scope

This checks **relative** links. External URL checking is deliberately out of
scope: it needs network access, tolerates flakiness badly, gets rate-limited,
and produces false failures that teach people to ignore the results. Keeping
this check hermetic is what makes it worth running on every push.

Proposals that would add a network call, a dependency, or a configuration file
are likely to be declined. Proposals that make the existing check more accurate
are very welcome.

## What a good change looks like

Every behavioural change needs a test that fails without it. The tests build
throwaway directory trees under `tmp_path`, so a new case is usually a few
lines:

```python
def test_something(self, tmp_path):
    write(tmp_path, "a.md", "[b](b.md)")
    write(tmp_path, "b.md", "# B")
    _, checked, broken = run(tmp_path)
    assert broken == []
```

If you are fixing a false positive, add the case that produced it. The
`TestCodeIsNotScanned` class exists because the tool reported four broken links
in its own README, and every case in it is a real thing that went wrong.

## Anchor accuracy

The slug rule in `_slugify` approximates GitHub's. It is not exhaustive — emoji
and some Unicode headings do not round-trip — which is why `--check-anchors` is
opt-in rather than default.

If you improve it, please include the heading that motivated the change as a
test case, and check the result against a real GitHub-rendered page rather than
against intuition. The rule is less obvious than it looks: punctuation is
stripped *before* spaces become hyphens, and the resulting whitespace runs are
not collapsed.

## Reporting a bug

Include the Markdown that reproduces it and what you expected. A one-line
repro against a two-file tree is worth more than a description of a large
repository.
