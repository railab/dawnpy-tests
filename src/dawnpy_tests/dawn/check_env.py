# tools/dawnpy-tests/src/dawnpy_tests/dawn/check_env.py
#
# SPDX-License-Identifier: Apache-2.0
#

"""Test environment checks."""

import subprocess


def check_test_environment() -> bool:
    """Check whether the test environment is ready (currently: can0)."""
    try:
        result = subprocess.run(
            ["ip", "link", "show", "can0"],
            capture_output=True,
            text=True,
            check=False,
        )
        return result.returncode == 0
    except FileNotFoundError:
        return False
