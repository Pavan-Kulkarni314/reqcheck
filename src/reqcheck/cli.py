"""Command line interface: reqcheck check | rules | convert."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from . import __version__
from .loaders import LoadError, load
from .report import CheckResult, to_console, to_html, to_markdown
from .rules import RULES, check_item
from .trace import analyse
from .writers import write


def run_check(path: str | Path, disabled: set[str] | None = None) -> CheckResult:
    project = load(path)
    quality = [f for item in project.items for f in check_item(item, disabled)]
    trace = analyse(project)
    if disabled:
        trace.findings = [f for f in trace.findings if f.rule not in disabled]
    return CheckResult(project, quality, trace)


def _cmd_check(args) -> int:
    try:
        result = run_check(args.file, set(args.disable or []))
    except (LoadError, OSError) as e:
        print(f"reqcheck: {e}", file=sys.stderr)
        return 2

    print(to_console(result, show_info=args.show_info))
    if args.html:
        Path(args.html).write_text(to_html(result), encoding="utf-8")
        print(f"\n  HTML report: {args.html}")
    if args.markdown:
        Path(args.markdown).write_text(to_markdown(result), encoding="utf-8")
        print(f"  Markdown report: {args.markdown}")

    failed = []
    if args.fail_on in ("error", "warning") and result.count("error"):
        failed.append(f"{result.count('error')} error(s)")
    if args.fail_on == "warning" and result.count("warning"):
        failed.append(f"{result.count('warning')} warning(s)")
    coverage = result.trace.coverage.requirements_verified
    if coverage < args.min_verification_coverage:
        failed.append(f"verification coverage {coverage:.1f} % is below {args.min_verification_coverage:.1f} %")
    if failed:
        print("\n  FAILED: " + "; ".join(failed))
        return 1
    print("\n  PASSED")
    return 0


def _cmd_rules(_args) -> int:
    print(f"{'Rule':16} {'Severity':9} Description")
    for rule in RULES:
        print(f"{rule.id:16} {rule.severity:9} {rule.description}")
    print("\nTraceability checks: DUPLICATE_ID, DANGLING_LINK, WRONG_LINK_TYPE, NO_PARENT, NO_CHILD, NOT_VERIFIED, ORPHAN_TEST")
    return 0


def _cmd_convert(args) -> int:
    try:
        project = load(args.file)
        write(project, args.output)
    except (LoadError, OSError, ValueError) as e:
        print(f"reqcheck: {e}", file=sys.stderr)
        return 2
    print(f"Wrote {len(project.items)} items to {args.output}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="reqcheck",
        description="Checks requirement quality and traceability in YAML, CSV or ReqIF files.",
    )
    parser.add_argument("--version", action="version", version=f"reqcheck {__version__}")
    sub = parser.add_subparsers(dest="command", required=True)

    check = sub.add_parser("check", help="Check a requirements file and write reports.")
    check.add_argument("file", help="Input file (.yaml, .csv or .reqif)")
    check.add_argument("--html", help="Write an HTML report to this path")
    check.add_argument("--markdown", help="Write a Markdown report to this path")
    check.add_argument("--fail-on", choices=["error", "warning", "never"], default="error",
                       help="Exit with code 1 if findings of this severity exist (default: error)")
    check.add_argument("--min-verification-coverage", type=float, default=0.0, metavar="PERCENT",
                       help="Exit with code 1 if fewer requirements than this are verified by tests")
    check.add_argument("--disable", nargs="*", metavar="RULE", help="Rule IDs to skip, e.g. PRONOUN NOT_EARS")
    check.add_argument("--show-info", action="store_true", help="Also print info-level findings")
    check.set_defaults(func=_cmd_check)

    rules = sub.add_parser("rules", help="List all rules.")
    rules.set_defaults(func=_cmd_rules)

    convert = sub.add_parser("convert", help="Convert between YAML, CSV and ReqIF.")
    convert.add_argument("file", help="Input file (.yaml, .csv or .reqif)")
    convert.add_argument("output", help="Output file (.yaml, .csv or .reqif)")
    convert.set_defaults(func=_cmd_convert)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
