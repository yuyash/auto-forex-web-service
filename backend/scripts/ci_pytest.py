"""Build and run backend pytest commands used by CI and git hooks."""

from __future__ import annotations

import argparse
import sys
from dataclasses import dataclass
from typing import Literal

SuiteName = Literal["unit", "integration", "e2e", "prepush"]

COMMON_ARGS = (
    "--override-ini",
    "addopts=",
    "--strict-markers",
    "--strict-config",
    "--import-mode=importlib",
    "--durations=10",
    "-v",
)


@dataclass(frozen=True)
class SuiteConfig:
    """Pytest settings that vary by backend test suite."""

    paths: tuple[str, ...]
    parallel_args: tuple[str, ...]
    timeout_args: tuple[str, ...] = ()
    default_args: tuple[str, ...] = ()


SUITES: dict[SuiteName, SuiteConfig] = {
    "unit": SuiteConfig(
        paths=("tests/unit/",),
        parallel_args=("-n", "auto", "--dist=loadscope"),
    ),
    "integration": SuiteConfig(
        paths=("tests/integration/",),
        parallel_args=("-n", "auto"),
        timeout_args=("--timeout=30",),
    ),
    "e2e": SuiteConfig(
        paths=("tests/e2e/",),
        parallel_args=("-n", "0"),
        timeout_args=("--timeout=300",),
    ),
    "prepush": SuiteConfig(
        paths=("tests/unit/", "tests/integration/"),
        parallel_args=("-n", "auto", "--dist=loadscope"),
        timeout_args=("--timeout=30",),
        default_args=("--tb=short",),
    ),
}


def build_pytest_args(
    suite: SuiteName,
    *,
    coverage: bool = False,
    coverage_append: bool = False,
    junitxml: str | None = None,
    extra_args: tuple[str, ...] = (),
) -> list[str]:
    """Return pytest arguments for a named backend test suite."""

    config = SUITES[suite]
    args = [
        *config.paths,
        *COMMON_ARGS,
        *config.parallel_args,
        *config.timeout_args,
        *config.default_args,
    ]

    if coverage:
        args.extend(("--cov=.", "--cov-report=xml", "--cov-report=html"))
        if coverage_append:
            args.append("--cov-append")

    if junitxml:
        args.append(f"--junitxml={junitxml}")

    args.extend(extra_args)
    return args


def parse_args(argv: list[str]) -> argparse.Namespace:
    """Parse command-line arguments for the CI pytest wrapper."""

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("suite", choices=sorted(SUITES))
    parser.add_argument("--coverage", action="store_true")
    parser.add_argument("--coverage-append", action="store_true")
    parser.add_argument("--junitxml")
    parser.add_argument(
        "extra_args",
        nargs=argparse.REMAINDER,
        help="additional pytest arguments, optionally after '--'",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    """Run pytest for the requested backend suite."""

    import pytest

    args = parse_args(sys.argv[1:] if argv is None else argv)
    extra_args = tuple(arg for arg in args.extra_args if arg != "--")
    pytest_args = build_pytest_args(
        args.suite,
        coverage=args.coverage,
        coverage_append=args.coverage_append,
        junitxml=args.junitxml,
        extra_args=extra_args,
    )
    return pytest.main(pytest_args)


if __name__ == "__main__":
    raise SystemExit(main())
