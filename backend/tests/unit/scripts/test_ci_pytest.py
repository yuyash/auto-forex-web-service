from scripts.ci_pytest import build_pytest_args


def test_unit_suite_uses_importlib_and_coverage_outputs() -> None:
    args = build_pytest_args(
        "unit",
        coverage=True,
        coverage_append=True,
        junitxml="junit-unit.xml",
    )

    assert args[:1] == ["tests/unit/"]
    assert args[args.index("--override-ini") + 1] == "addopts="
    assert "--import-mode=importlib" in args
    assert ("-n" in args) and (args[args.index("-n") + 1] == "auto")
    assert "--dist=loadscope" in args
    assert "--cov=." in args
    assert "--cov-append" in args
    assert "--junitxml=junit-unit.xml" in args


def test_e2e_suite_runs_serially_with_long_timeout() -> None:
    args = build_pytest_args("e2e", junitxml="junit-e2e.xml")

    assert args[:1] == ["tests/e2e/"]
    assert args[args.index("-n") + 1] == "0"
    assert "--timeout=300" in args
    assert "--junitxml=junit-e2e.xml" in args


def test_prepush_suite_matches_backend_hook_scope() -> None:
    args = build_pytest_args("prepush")

    assert args[:2] == ["tests/unit/", "tests/integration/"]
    assert "--import-mode=importlib" in args
    assert "--timeout=30" in args
    assert "--tb=short" in args
