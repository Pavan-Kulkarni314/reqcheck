from pathlib import Path

from reqcheck.cli import main

EXAMPLES = Path(__file__).parent.parent / "examples"
ACC = str(EXAMPLES / "acc_requirements.yaml")
DRAFT = str(EXAMPLES / "draft_lka_requirements.csv")


def test_acc_example_passes_by_default(capsys):
    assert main(["check", ACC]) == 0
    assert "PASSED" in capsys.readouterr().out


def test_draft_example_fails_on_errors(capsys):
    assert main(["check", DRAFT]) == 1
    assert "FAILED" in capsys.readouterr().out


def test_fail_on_never_always_passes():
    assert main(["check", DRAFT, "--fail-on", "never"]) == 0


def test_fail_on_warning_and_coverage_gate():
    assert main(["check", ACC, "--fail-on", "warning"]) == 1
    assert main(["check", ACC, "--min-verification-coverage", "100"]) == 1
    assert main(["check", ACC, "--min-verification-coverage", "80"]) == 0


def test_reports_are_written(tmp_path):
    html, md = tmp_path / "r.html", tmp_path / "r.md"
    main(["check", DRAFT, "--html", str(html), "--markdown", str(md), "--fail-on", "never"])
    page = html.read_text(encoding="utf-8")
    assert "<!DOCTYPE html>" in page and "SYS-107" in page and "DANGLING_LINK" in page
    assert "## Traceability matrix" in md.read_text(encoding="utf-8")


def test_missing_file_returns_2(capsys):
    assert main(["check", "does_not_exist.yaml"]) == 2


def test_convert_and_rules(tmp_path, capsys):
    out = tmp_path / "acc.reqif"
    assert main(["convert", ACC, str(out)]) == 0
    assert out.read_text(encoding="utf-8").startswith("<?xml")
    assert main(["rules"]) == 0
    assert "VAGUE_TERM" in capsys.readouterr().out
