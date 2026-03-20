#!/usr/bin/env python3
#
# SPDX-License-Identifier: Apache-2.0
#

"""Shared fixtures for standalone dawnpy-tests package tests."""

from pathlib import Path
from types import SimpleNamespace

import pytest


@pytest.fixture
def patch_project_resolve(monkeypatch):
    """Patch Project.resolve for tests that create a fake Dawn project."""

    def _patch(project_root: Path):
        root = project_root.resolve()

        def _fake_resolve(start_path=None, **_kwargs):
            return SimpleNamespace(
                project_root=root,
                dawn_root=root,
                nuttx_dir=root / "external" / "nuttx",
                nuttx_apps_dir=root / "external" / "apps",
                is_oot=False,
                cmake_env=lambda: {
                    "DAWN_BOARDS_COMMON": str(root / "boards" / "common"),
                    "DAWN_EXTENSION_APPS_KCONFIG": str(
                        root / ".dawn-no-extension-apps.Kconfig"
                    ),
                },
            )

        monkeypatch.setattr(
            "dawnpy_tests.dawn.test_utils.Project.resolve", _fake_resolve
        )

    return _patch
