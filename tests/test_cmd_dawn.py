# tools/dawnpy/tests/test_cmd_dawn.py
#
# SPDX-License-Identifier: Apache-2.0
#

"""Tests for the Dawn CLI command module."""

from pathlib import Path

import pytest

from dawnpy_tests.commands.cmd_test import do_cmd_test


def test_cmd_test_arg_validation(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(
        "dawnpy_tests.commands.cmd_test._resolve_test_context",
        lambda *a, **k: (tmp_path, tmp_path / "config", tmp_path / "manifest"),
    )
    monkeypatch.setattr(
        "dawnpy_tests.commands.cmd_test._validate_project_root",
        lambda *a: True,
    )

    with pytest.raises(SystemExit):
        do_cmd_test(
            "config",
            "root",
            "test_dir",
            60,
            None,
            True,
            True,
            False,
            True,
            "list",
        )

    with pytest.raises(SystemExit):
        # ntfc_only and skip_ntfc
        do_cmd_test(
            "config",
            "root",
            "test_dir",
            60,
            None,
            True,
            False,
            True,
            True,
            "list",
        )

    with pytest.raises(SystemExit):
        # size_only and ntfc_only
        do_cmd_test(
            "config",
            "root",
            "test_dir",
            60,
            None,
            True,
            False,
            False,
            True,
            "list",
            True,
        )

    with pytest.raises(SystemExit):
        # size_only and batch_only
        do_cmd_test(
            "config",
            "root",
            "test_dir",
            60,
            None,
            True,
            True,
            False,
            False,
            "list",
            True,
        )

    with pytest.raises(SystemExit):
        # size_only and skip_ntfc
        do_cmd_test(
            "config",
            "root",
            "test_dir",
            60,
            None,
            True,
            False,
            True,
            False,
            "list",
            True,
        )


def test_cmd_test_root_validation(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "dawnpy_tests.commands.cmd_test._resolve_test_context",
        lambda *a, **k: (Path("root"), Path("config"), Path("manifest")),
    )
    monkeypatch.setattr(
        "dawnpy_tests.commands.cmd_test._validate_project_root",
        lambda *a: False,
    )
    with pytest.raises(SystemExit):
        do_cmd_test(
            "config",
            "root",
            "test_dir",
            60,
            None,
            True,
            False,
            False,
            False,
            "list",
        )


def test_cmd_test_prerequisites(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    from dawnpy_tests.commands.cmd_test import do_cmd_test

    monkeypatch.setattr(
        "dawnpy_tests.commands.cmd_test._resolve_test_context",
        lambda *a, **k: (tmp_path, tmp_path / "config", tmp_path / "manifest"),
    )
    monkeypatch.setattr(
        "dawnpy_tests.commands.cmd_test._validate_project_root",
        lambda *a: True,
    )
    monkeypatch.setattr(
        "dawnpy_tests.commands.cmd_test.check_test_environment", lambda: False
    )

    with pytest.raises(SystemExit):
        do_cmd_test(
            "config",
            "root",
            "test_dir",
            60,
            None,
            True,
            False,
            False,
            False,
            "list",
        )

    captured = capsys.readouterr()
    assert "missing 'can0' interface" in captured.out


def test_cmd_test_success(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    from dawnpy_tests.commands.cmd_test import do_cmd_test

    monkeypatch.setattr(
        "dawnpy_tests.commands.cmd_test._validate_project_root",
        lambda *a: True,
    )
    monkeypatch.setattr(
        "dawnpy_tests.commands.cmd_test.check_test_environment", lambda: True
    )
    monkeypatch.setattr(
        "dawnpy_tests.commands.cmd_test.build_test_steps",
        lambda *a, **k: [],
    )
    monkeypatch.setattr(
        "dawnpy_tests.commands.cmd_test._resolve_test_context",
        lambda *a, **k: (tmp_path, tmp_path / "config", tmp_path / "manifest"),
    )

    do_cmd_test(
        "config",
        "root",
        "test_dir",
        60,
        None,
        True,
        False,
        False,
        False,
        "list",
    )


def test_cmd_test_size_only_skips_prerequisites(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    from dawnpy_tests.commands.cmd_test import do_cmd_test

    monkeypatch.setattr(
        "dawnpy_tests.commands.cmd_test._validate_project_root",
        lambda *a: True,
    )
    monkeypatch.setattr(
        "dawnpy_tests.commands.cmd_test._resolve_test_context",
        lambda *a, **k: (tmp_path, tmp_path / "config", tmp_path / "manifest"),
    )

    def fail_if_called():
        raise AssertionError("check_test_environment should not be called")

    monkeypatch.setattr(
        "dawnpy_tests.commands.cmd_test.check_test_environment",
        fail_if_called,
    )
    monkeypatch.setattr(
        "dawnpy_tests.commands.cmd_test.build_test_steps",
        lambda *a, **k: [],
    )

    do_cmd_test(
        "config",
        "root",
        "test_dir",
        60,
        None,
        True,
        False,
        False,
        False,
        "list",
        True,
    )


def test_cmd_test_step_failure(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    from dawnpy_tests.commands.cmd_test import do_cmd_test

    monkeypatch.setattr(
        "dawnpy_tests.commands.cmd_test._validate_project_root",
        lambda *a: True,
    )
    monkeypatch.setattr(
        "dawnpy_tests.commands.cmd_test.check_test_environment", lambda: True
    )
    monkeypatch.setattr(
        "dawnpy_tests.commands.cmd_test._resolve_test_context",
        lambda *a, **k: (tmp_path, tmp_path / "config", tmp_path / "manifest"),
    )

    step = {
        "name": "fail",
        "enabled": True,
        "function": lambda *a: False,
        "args": [],
    }
    monkeypatch.setattr(
        "dawnpy_tests.commands.cmd_test.build_test_steps",
        lambda *a, **k: [step],
    )

    with pytest.raises(SystemExit):
        do_cmd_test(
            "config",
            "root",
            "test_dir",
            60,
            None,
            True,
            False,
            False,
            False,
            "list",
        )


def test_cmd_test_step_skipped(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    from dawnpy_tests.commands.cmd_test import do_cmd_test

    monkeypatch.setattr(
        "dawnpy_tests.commands.cmd_test._validate_project_root",
        lambda *a: True,
    )
    monkeypatch.setattr(
        "dawnpy_tests.commands.cmd_test.check_test_environment", lambda: True
    )
    monkeypatch.setattr(
        "dawnpy_tests.commands.cmd_test._resolve_test_context",
        lambda *a, **k: (tmp_path, tmp_path / "config", tmp_path / "manifest"),
    )

    step = {
        "name": "skip",
        "enabled": False,
        "function": lambda *a: False,
        "args": [],
    }
    monkeypatch.setattr(
        "dawnpy_tests.commands.cmd_test.build_test_steps",
        lambda *a, **k: [step],
    )

    do_cmd_test(
        "config",
        "root",
        "test_dir",
        60,
        None,
        True,
        False,
        False,
        False,
        "list",
    )


def test_cmd_test_summary_prints_enabled_step_timing(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    from dawnpy_tests.commands.cmd_test import do_cmd_test

    monkeypatch.setattr(
        "dawnpy_tests.commands.cmd_test._validate_project_root",
        lambda *a: True,
    )
    monkeypatch.setattr(
        "dawnpy_tests.commands.cmd_test.check_test_environment", lambda: True
    )
    monkeypatch.setattr(
        "dawnpy_tests.commands.cmd_test._resolve_test_context",
        lambda *a, **k: (tmp_path, tmp_path / "config", tmp_path / "manifest"),
    )

    steps = [
        {
            "name": "run_a",
            "enabled": True,
            "function": lambda *a: True,
            "args": [],
        },
        {
            "name": "filtered",
            "enabled": False,
            "function": lambda *a: False,
            "args": [],
        },
        {
            "name": "run_b",
            "enabled": True,
            "function": lambda *a: True,
            "args": [],
        },
    ]
    monkeypatch.setattr(
        "dawnpy_tests.commands.cmd_test.build_test_steps",
        lambda *a, **k: steps,
    )
    times = iter([10.0, 12.5, 20.0, 21.25])
    monkeypatch.setattr(
        "dawnpy_tests.commands.cmd_test.perf_counter", lambda: next(times)
    )

    do_cmd_test(
        "config",
        "root",
        "test_dir",
        60,
        None,
        False,
        False,
        False,
        False,
        "list",
    )

    captured = capsys.readouterr()
    assert "run_a: 2.50s" in captured.out
    assert "run_b: 1.25s" in captured.out
    assert "filtered" not in captured.out
    assert "Total execution time: 3.75s" in captured.out


def test_resolve_default_path_prefers_cwd(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from dawnpy_tests.commands.cmd_test import _resolve_default_path

    monkeypatch.chdir(tmp_path)
    local = tmp_path / "ntfc" / "manifest-host.yaml"
    local.parent.mkdir(parents=True)
    local.write_text("sessions: []\n", encoding="utf-8")

    dawn_root = tmp_path / "repo"
    dawn_root.mkdir()

    assert _resolve_default_path("ntfc/manifest-host.yaml", dawn_root) == local


def test_normalize_ntfc_manifest_preserves_ntfc_path_semantics(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, patch_project_resolve
) -> None:
    from dawnpy_tests.dawn.test_utils import _normalize_ntfc_manifest

    root = tmp_path / "proj"
    manifest = root / "ntfc" / "manifest.yaml"
    config = root / "ntfc" / "configs" / "sim" / "tests" / "config.yaml"
    testpath = root / "ntfc" / "tests" / "tests"
    defconfig = (
        root / "boards" / "sim" / "sim" / "sim" / "configs" / "nsh_tests"
    )
    nuttx = root / "external" / "nuttx"

    testpath.mkdir(parents=True)
    defconfig.mkdir(parents=True)
    (defconfig / "defconfig").write_text("", encoding="utf-8")
    nuttx.mkdir(parents=True)
    manifest.parent.mkdir(parents=True, exist_ok=True)
    config.parent.mkdir(parents=True, exist_ok=True)
    patch_project_resolve(root)

    manifest.write_text(
        "sessions:\n"
        "  - name: sim-tests\n"
        "    confpath: ntfc/configs/sim/tests/config.yaml\n"
        "    testpath: ntfc/tests/tests\n",
        encoding="utf-8",
    )
    config.write_text(
        "config:\n"
        "  cwd: ./external\n"
        "  build_dir: ./build\n"
        "product:\n"
        "  name: demo\n"
        "  cores:\n"
        "    core0:\n"
        "      name: main\n"
        "      device: sim\n"
        "      defconfig: ../../boards/sim/sim/sim/configs/nsh_tests\n",
        encoding="utf-8",
    )

    monkeypatch.chdir(root)
    normalized = _normalize_ntfc_manifest(manifest)
    content = normalized.read_text(encoding="utf-8")
    normalized_confpath = Path(
        content.split("confpath: ", 1)[1].splitlines()[0]
    )
    normalized_config = normalized_confpath.read_text(encoding="utf-8")

    assert str(config) not in content
    assert str(testpath) in content
    assert str(defconfig) in normalized_config
