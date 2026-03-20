# tools/dawnpy-tests/src/dawnpy_tests/commands/cmd_test.py
#
# SPDX-License-Identifier: Apache-2.0
#

"""Module containing the test command for Dawn."""

from pathlib import Path

import click
from dawnpy.cli.options import configure_cli_logging
from dawnpy.dawn.output import (
    colored,
    print_error,
    print_header,
    print_info,
    print_success,
    print_verbose,
    print_warning,
)
from dawnpy.dawn.project import Project
from dawnpy.sources import DawnSourcesMissing

from dawnpy_tests.dawn.check_env import check_test_environment
from dawnpy_tests.dawn.test_steps import StepDefinition, build_test_steps


def _resolve_default_path(path_str: str, dawn_root: Path) -> Path:
    """Resolve a CLI path, preferring cwd-local files over repo defaults."""
    path = Path(path_str)
    if path.is_absolute():
        return path

    cwd_candidate = (Path.cwd() / path).resolve()
    if cwd_candidate.exists():
        return cwd_candidate

    return (dawn_root / path).resolve()


def _resolve_test_context(
    config_file: str, ntfc_list: str
) -> tuple[Path, Path, Path]:
    """Resolve active config/manifest paths and the workspace root."""
    dawn_root = Project.resolve().dawn_root
    config_path = _resolve_default_path(config_file, dawn_root)
    manifest_path = _resolve_default_path(ntfc_list, dawn_root)

    context_candidates: list[Path] = []
    for candidate in (config_path, manifest_path):
        found = Project.resolve(candidate).project_root
        if found.exists():
            context_candidates.append(found)

    project_root = context_candidates[0] if context_candidates else dawn_root
    return project_root, config_path, manifest_path


def _validate_project_root(project_root: Path, verbose: bool) -> bool:
    """Validate that dawnpy can resolve the requested project root."""
    try:
        resolved = Project.resolve(project_root)
    except DawnSourcesMissing as exc:
        print_error(str(exc))
        return False

    if resolved.project_root != project_root:
        print_error(f"Invalid Dawn project root: {project_root}")
        print_info("Run dawnpy-tests from a Dawn project root.")
        return False

    print_verbose(f"Dawn project root: {resolved.project_root}", verbose)
    print_verbose(f"Dawn source root: {resolved.dawn_root}", verbose)
    return True


def _validate_test_args(
    ntfc_only: bool, batch_only: bool, skip_ntfc: bool, size_only: bool
) -> None:
    """Validate command line arguments for test command."""
    if ntfc_only and batch_only:
        print_error("--ntfc-only cannot be combined with --batch-only")
        raise SystemExit(1)
    if ntfc_only and skip_ntfc:
        print_error("--ntfc-only cannot be combined with --skip-ntfc")
        raise SystemExit(1)
    if size_only and ntfc_only:
        print_error("--size-only cannot be combined with --ntfc-only")
        raise SystemExit(1)
    if size_only and batch_only:
        print_error("--size-only cannot be combined with --batch-only")
        raise SystemExit(1)
    if size_only and skip_ntfc:
        print_error("--size-only cannot be combined with --skip-ntfc")
        raise SystemExit(1)


def _check_test_prerequisites() -> None:
    """Check test environment prerequisites."""
    print_info("Checking test environment prerequisites...")
    if not check_test_environment():
        print_warning(
            "Test environment is not ready (missing 'can0' interface)"
        )
        print_info("To create a virtual CAN interface, run:")
        click.echo()
        click.echo("  sh ./testenv_init.sh")
        click.echo()
        print_info("Then retry the test command")
        raise SystemExit(1)
    else:
        print_success("Test environment is ready")


def _run_test_steps(
    test_steps: list[StepDefinition], verbose: bool
) -> list[str]:
    """Execute enabled test steps and return list of failed steps."""
    failed_steps: list[str] = []
    for step in test_steps:
        if not step["enabled"]:
            print_verbose(f"Skipping step: {step['name']}", verbose)
            continue

        click.echo()
        step_result = step["function"](*step["args"])

        if not step_result:
            failed_steps.append(step["name"])
            click.echo()
            print_error(
                f"Test step failed: {step['name']}"
            )  # pragma: no cover
            click.echo()
            break
        else:
            click.echo()  # pragma: no cover
    return failed_steps


def _print_test_summary(
    test_steps: list[StepDefinition], failed_steps: list[str]
) -> None:
    """Print final test execution summary."""
    click.echo()
    print_header("Test Summary")

    total_steps = len([s for s in test_steps if s["enabled"]])
    passed_steps = total_steps - len(failed_steps)

    click.echo(f"Total test steps: {total_steps}")
    click.echo(colored(f"Passed: {passed_steps}", "green"))
    if failed_steps:
        click.echo(colored(f"Failed: {len(failed_steps)}", "red"))
        click.echo()
        click.echo("Failed steps:")
        for step_name in failed_steps:
            click.echo(f"  {colored('[ERR]', 'red')} {step_name}")

    click.echo()


def do_cmd_test(
    config_file: str,
    build_root: str,
    test_build_dir: str,
    test_timeout: int,
    jobs: int | None,
    verbose: bool,
    batch_only: bool,
    skip_ntfc: bool,
    ntfc_only: bool,
    ntfc_list: str,
    size_only: bool = False,
) -> None:
    """Logic implementation for Dawn project test command."""
    print_header("Dawn Project Test Suite")

    project_root, config_path, manifest_path = _resolve_test_context(
        config_file, ntfc_list
    )

    if not _validate_project_root(project_root, verbose):
        raise SystemExit(1)

    _validate_test_args(ntfc_only, batch_only, skip_ntfc, size_only)

    if not size_only:
        click.echo()
        _check_test_prerequisites()
        click.echo()

    test_steps = build_test_steps(
        project_root,
        str(config_path),
        build_root,
        test_build_dir,
        test_timeout,
        jobs,
        verbose,
        batch_only,
        skip_ntfc,
        str(manifest_path),
        ntfc_only,
        size_only,
    )

    failed_steps = _run_test_steps(test_steps, verbose)
    _print_test_summary(test_steps, failed_steps)

    if failed_steps:
        raise SystemExit(1)
    else:
        print_success("All tests passed!")
        click.echo()


@click.command(name="test")
@click.option(
    "-c",
    "--config-file",
    default="tools/config-build-all.txt",
    show_default=True,
    help="Path to batch build configuration file",
)
@click.option(
    "--build-root",
    default="build",
    show_default=True,
    help="Root directory for build directories",
)
@click.option(
    "--test-build-dir",
    default="build-sim-sim-tests",
    show_default=True,
    help="Build directory name for simulator tests",
)
@click.option(
    "--test-timeout",
    type=int,
    default=60,
    show_default=True,
    help="Test execution timeout in seconds",
)
@click.option(
    "-j",
    "--jobs",
    type=int,
    help="Number of parallel build jobs",
)
@click.option(
    "-v",
    "--verbose",
    is_flag=True,
    help="Verbose output",
)
@click.option(
    "--batch-only",
    is_flag=True,
    help="Run only batch build and analysis (skip simulator tests)",
)
@click.option(
    "--skip-ntfc",
    is_flag=True,
    help="Skip NTFC test step",
)
@click.option(
    "--ntfc-only",
    is_flag=True,
    help="Run only NTFC test step",
)
@click.option(
    "--ntfc-list",
    default="ntfc/manifest-host.yaml",
    show_default=True,
    help="Path to NTFC manifest YAML file",
)
@click.option(
    "--size-only",
    is_flag=True,
    help="Run only build size analysis step",
)
@click.option(
    "--debug/--no-debug",
    default=False,
    is_flag=True,
    envvar="DAWNPY_DEBUG",
)
def cmd_test(
    config_file: str,
    build_root: str,
    test_build_dir: str,
    test_timeout: int,
    jobs: int | None,
    verbose: bool,
    batch_only: bool,
    skip_ntfc: bool,
    ntfc_only: bool,
    ntfc_list: str,
    size_only: bool,
    debug: bool,
) -> None:
    """Run project tests."""
    configure_cli_logging(debug)

    do_cmd_test(  # pragma: no cover
        config_file,
        build_root,
        test_build_dir,
        test_timeout,
        jobs,
        verbose,
        batch_only,
        skip_ntfc,
        ntfc_only,
        ntfc_list,
        size_only,
    )
