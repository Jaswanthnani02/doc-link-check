"""Tests for doc_link_check.

Each test builds a throwaway directory tree, so nothing depends on the
repository this happens to live in.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import doc_link_check as dlc  # noqa: E402


def write(root: Path, rel: str, text: str) -> Path:
    path = root / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


def run(root: Path, **kwargs):
    opts = {"ignores": set(dlc.DEFAULT_IGNORES), "use_git": False, "check_anchors": False}
    opts.update(kwargs)
    return dlc.check(root, **opts)


class TestResolution:
    def test_resolving_link_passes(self, tmp_path):
        write(tmp_path, "a.md", "see [b](b.md)")
        write(tmp_path, "b.md", "# B")
        _, checked, broken = run(tmp_path)
        assert checked == 1
        assert broken == []

    def test_missing_target_is_reported(self, tmp_path):
        write(tmp_path, "a.md", "see [gone](missing.md)")
        _, _, broken = run(tmp_path)
        assert len(broken) == 1
        rel, lineno, target, why = broken[0]
        assert (rel, lineno, target) == ("a.md", 1, "missing.md")
        assert "does not exist" in why

    def test_link_is_resolved_relative_to_its_own_file(self, tmp_path):
        write(tmp_path, "docs/guide.md", "up to [root](../README.md)")
        write(tmp_path, "README.md", "# Root")
        _, _, broken = run(tmp_path)
        assert broken == []

    def test_directory_target_resolves(self, tmp_path):
        write(tmp_path, "a.md", "see [runbooks](runbooks/)")
        (tmp_path / "runbooks").mkdir()
        _, _, broken = run(tmp_path)
        assert broken == []

    def test_line_number_is_accurate(self, tmp_path):
        write(tmp_path, "a.md", "one\ntwo\n[x](nope.md)\n")
        _, _, broken = run(tmp_path)
        assert broken[0][1] == 3


class TestExternalLinks:
    @pytest.mark.parametrize("target", [
        "https://example.com/x",
        "http://example.com",
        "mailto:someone@example.com",
        "tel:+15555550100",
        "//cdn.example.com/x.png",
    ])
    def test_external_links_are_never_fetched_or_counted(self, tmp_path, target):
        write(tmp_path, "a.md", f"see [x]({target})")
        _, checked, broken = run(tmp_path)
        assert checked == 0
        assert broken == []


class TestSyntaxVariants:
    def test_angle_bracket_target(self, tmp_path):
        write(tmp_path, "a.md", "see [b](<b.md>)")
        write(tmp_path, "b.md", "# B")
        _, checked, broken = run(tmp_path)
        assert checked == 1 and broken == []

    def test_target_with_title(self, tmp_path):
        write(tmp_path, "a.md", '[b](b.md "The B file")')
        write(tmp_path, "b.md", "# B")
        _, _, broken = run(tmp_path)
        assert broken == []

    def test_reference_style_definition(self, tmp_path):
        write(tmp_path, "a.md", "see [b][ref]\n\n[ref]: b.md\n")
        write(tmp_path, "b.md", "# B")
        _, checked, broken = run(tmp_path)
        assert checked == 1 and broken == []

    def test_image_with_missing_file_is_reported(self, tmp_path):
        write(tmp_path, "a.md", "![diagram](img/arch.png)")
        _, _, broken = run(tmp_path)
        assert len(broken) == 1

    def test_multiple_links_on_one_line(self, tmp_path):
        write(tmp_path, "a.md", "[b](b.md) and [c](c.md)")
        write(tmp_path, "b.md", "# B")
        _, checked, broken = run(tmp_path)
        assert checked == 2
        assert len(broken) == 1 and broken[0][2] == "c.md"


class TestAnchors:
    def test_anchor_ignored_by_default(self, tmp_path):
        write(tmp_path, "a.md", "[b](b.md#nonexistent)")
        write(tmp_path, "b.md", "# B")
        _, _, broken = run(tmp_path)
        assert broken == []

    def test_anchor_checked_when_requested(self, tmp_path):
        write(tmp_path, "a.md", "[b](b.md#nonexistent)")
        write(tmp_path, "b.md", "# B")
        _, _, broken = run(tmp_path, check_anchors=True)
        assert len(broken) == 1
        assert "no such heading" in broken[0][3]

    def test_matching_anchor_passes(self, tmp_path):
        write(tmp_path, "a.md", "[b](b.md#threshold-tuning-history)")
        write(tmp_path, "b.md", "## Threshold tuning history\n")
        _, _, broken = run(tmp_path, check_anchors=True)
        assert broken == []

    def test_same_file_anchor(self, tmp_path):
        write(tmp_path, "a.md", "[up](#setup)\n\n## Setup\n")
        _, _, broken = run(tmp_path, check_anchors=True)
        assert broken == []

    def test_github_line_reference_is_not_treated_as_a_heading(self, tmp_path):
        write(tmp_path, "a.md", "[code](b.md#L42)")
        write(tmp_path, "b.md", "# B")
        _, _, broken = run(tmp_path, check_anchors=True)
        assert broken == []

    def test_explicit_html_anchor_counts(self, tmp_path):
        write(tmp_path, "a.md", '[x](b.md#custom)')
        write(tmp_path, "b.md", '<a id="custom"></a>\n# B\n')
        _, _, broken = run(tmp_path, check_anchors=True)
        assert broken == []


class TestCodeIsNotScanned:
    """Link syntax inside code is documentation about links, not a link.

    This class exists because the tool reported four broken links in its own
    README, all of them example syntax.
    """

    def test_inline_code_span_is_ignored(self, tmp_path):
        write(tmp_path, "a.md", "Inline links `[text](target)` are supported.")
        _, checked, broken = run(tmp_path)
        assert checked == 0 and broken == []

    def test_fenced_block_is_ignored(self, tmp_path):
        write(tmp_path, "a.md", "before\n\n```\n[x](nope.md)\n```\n\nafter\n")
        _, checked, broken = run(tmp_path)
        assert checked == 0 and broken == []

    def test_fenced_block_with_language_is_ignored(self, tmp_path):
        write(tmp_path, "a.md", "```markdown\n[x](nope.md)\n```\n")
        _, _, broken = run(tmp_path)
        assert broken == []

    def test_tilde_fence_is_ignored(self, tmp_path):
        write(tmp_path, "a.md", "~~~\n[x](nope.md)\n~~~\n")
        _, _, broken = run(tmp_path)
        assert broken == []

    def test_backtick_fence_is_not_closed_by_a_tilde_fence(self, tmp_path):
        write(tmp_path, "a.md", "```\n~~~\n[x](nope.md)\n```\n")
        _, _, broken = run(tmp_path)
        assert broken == []

    def test_real_links_outside_code_still_checked(self, tmp_path):
        write(tmp_path, "a.md", "```\n[ignored](nope.md)\n```\n\nreal [b](missing.md)\n")
        _, checked, broken = run(tmp_path)
        assert checked == 1
        assert len(broken) == 1 and broken[0][2] == "missing.md"

    def test_line_numbers_survive_stripping(self, tmp_path):
        write(tmp_path, "a.md", "```\ncode\n```\n\n[x](nope.md)\n")
        _, _, broken = run(tmp_path)
        assert broken[0][1] == 5

    def test_heading_inside_a_fence_is_not_an_anchor(self, tmp_path):
        write(tmp_path, "a.md", "[x](b.md#install)")
        write(tmp_path, "b.md", "```bash\n# Install\n```\n")
        _, _, broken = run(tmp_path, check_anchors=True)
        assert len(broken) == 1


class TestIgnores:
    def test_default_ignores_are_skipped(self, tmp_path):
        write(tmp_path, "node_modules/pkg/README.md", "[x](nope.md)")
        write(tmp_path, "a.md", "# A")
        files, _, broken = run(tmp_path)
        assert broken == []
        assert all("node_modules" not in f.as_posix() for f in files)

    def test_extra_ignore_is_honoured(self, tmp_path):
        write(tmp_path, "archive/old.md", "[x](nope.md)")
        write(tmp_path, "a.md", "# A")
        _, _, broken = run(tmp_path, ignores=set(dlc.DEFAULT_IGNORES) | {"archive"})
        assert broken == []


class TestCli:
    def test_exit_zero_when_clean(self, tmp_path, capsys):
        write(tmp_path, "a.md", "[b](b.md)")
        write(tmp_path, "b.md", "# B")
        assert dlc.main([str(tmp_path), "--no-git"]) == 0
        assert "OK:" in capsys.readouterr().out

    def test_exit_one_when_broken(self, tmp_path, capsys):
        write(tmp_path, "a.md", "[b](missing.md)")
        assert dlc.main([str(tmp_path), "--no-git"]) == 1
        assert "missing.md" in capsys.readouterr().err

    def test_quiet_suppresses_success_output(self, tmp_path, capsys):
        write(tmp_path, "a.md", "# A")
        assert dlc.main([str(tmp_path), "--no-git", "--quiet"]) == 0
        assert capsys.readouterr().out == ""

    def test_missing_directory_exits_two(self, tmp_path, capsys):
        assert dlc.main([str(tmp_path / "nope"), "--no-git"]) == 2
        assert "not a directory" in capsys.readouterr().err

    def test_empty_project_is_not_a_failure(self, tmp_path):
        assert dlc.main([str(tmp_path), "--no-git"]) == 0


class TestRobustness:
    def test_non_utf8_file_does_not_crash(self, tmp_path):
        (tmp_path / "bad.md").write_bytes(b"\xff\xfe binary \x00")
        write(tmp_path, "a.md", "# A")
        _, _, broken = run(tmp_path)
        assert broken == []

    def test_slugify_matches_common_github_cases(self):
        assert dlc._slugify("## Threshold tuning history") == "threshold-tuning-history"
        assert dlc._slugify("# What's New?") == "whats-new"
        assert dlc._slugify("### CI / CD") == "ci--cd"
