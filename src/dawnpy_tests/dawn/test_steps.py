# tools/dawnpy-tests/src/dawnpy_tests/dawn/test_steps.py
#
# SPDX-License-Identifier: Apache-2.0
#

"""Test step composition for Dawn CLI."""

from collections.abc import Callable
from pathlib import Path
from typing import Any, TypedDict

from dawnpy_tests.dawn.test_utils import (
    analyze_build_sizes,
    run_batch_build,
    run_batch_build_if_missing,
    run_cppcheck,
    run_format_check,
    run_ntfc_tests,
    run_ntfc_tox,
    run_simulator_tests,
)


class StepDefinition(TypedDict):
    """Single test step definition for the test command."""

    name: str
    enabled: bool
    function: Callable[..., bool]
    args: list[Any]


def build_test_steps(
    project_root: Path,
    config_file: str,
    build_root: str,
    test_build_dir: str,
    test_timeout: int,
    jobs: int | None,
    verbose: bool,
    batch_only: bool,
    skip_ntfc: bool = False,
    ntfc_list: str = "ntfc/manifest-host.yaml",
    ntfc_only: bool = False,
    size_only: bool = False,
) -> list[StepDefinition]:
    """Build the ordered list of test steps for the Dawn test command."""
    return [
        {
            "name": "format_check",
            "enabled": (not ntfc_only) and (not size_only),
            "function": run_format_check,
            "args": [project_root, verbose],
        },
        {
            "name": "cppcheck",
            "enabled": (not ntfc_only) and (not size_only),
            "function": run_cppcheck,
            "args": [project_root, verbose],
        },
        {
            "name": "ntfc_tox",
            "enabled": (not batch_only)
            and (not skip_ntfc)
            and (not size_only),
            "function": run_ntfc_tox,
            "args": [project_root, verbose],
        },
        {
            "name": "batch_build",
            "enabled": not ntfc_only,
            "function": (
                run_batch_build_if_missing if size_only else run_batch_build
            ),
            "args": [config_file, project_root, verbose, build_root, jobs],
        },
        {
            "name": "simulator_tests",
            "enabled": (not ntfc_only)
            and (not batch_only)
            and (not size_only),
            "function": run_simulator_tests,
            "args": [
                project_root / build_root / test_build_dir,
                project_root,
                test_timeout,
            ],
        },
        {
            "name": "ntfc_tests",
            "enabled": (not batch_only)
            and (not skip_ntfc)
            and (not size_only),
            "function": run_ntfc_tests,
            "args": [project_root, Path(ntfc_list), verbose],
        },
        {
            "name": "build_size_analysis",
            "enabled": not ntfc_only,
            "function": analyze_build_sizes,
            "args": [project_root / build_root, project_root, verbose],
        },
    ]
