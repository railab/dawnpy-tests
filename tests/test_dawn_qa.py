# tools/dawnpy-tests/tests/test_dawn_qa.py
#
# SPDX-License-Identifier: Apache-2.0
#

"""Tests for dawnpy-tests QA helpers (check_env, test_steps, test_utils)."""

import subprocess
from pathlib import Path

import pytest

from dawnpy_tests.dawn.check_env import check_test_environment
from dawnpy_tests.dawn.test_steps import build_test_steps
from dawnpy_tests.dawn.test_utils import (
    _dawnpy_env,
    _emit_remaining_output,
    analyze_build_sizes,
    get_arm_binary_size,
    run_batch_build,
    run_batch_build_if_missing,
    run_cppcheck,
    run_format_check,
    run_ntfc_tests,
    run_simulator_tests,
)


def test_check_test_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    class Result:
        returncode = 0

    monkeypatch.setattr(subprocess, "run", lambda *a, **k: Result())
    assert check_test_environment() is True

    class BadResult:
        returncode = 1

    monkeypatch.setattr(subprocess, "run", lambda *a, **k: BadResult())
    assert check_test_environment() is False

    def raise_missing(*args, **kwargs):
        raise FileNotFoundError

    monkeypatch.setattr(subprocess, "run", raise_missing)
    assert check_test_environment() is False


def test_test_steps_builder(tmp_path: Path) -> None:
    steps = build_test_steps(
        tmp_path, "config.txt", "build", "tests", 60, 2, True, False
    )
    names = [s["name"] for s in steps]
    assert names == [
        "format_check",
        "cppcheck",
        "ntfc_tox",
        "batch_build",
        "simulator_tests",
        "ntfc_tests",
        "build_size_analysis",
    ]
    enabled_default = {s["name"]: s["enabled"] for s in steps}
    assert enabled_default["format_check"] is True
    assert enabled_default["cppcheck"] is True
    assert enabled_default["batch_build"] is True
    assert enabled_default["simulator_tests"] is True
    assert enabled_default["build_size_analysis"] is True
    batch_step = next(s for s in steps if s["name"] == "batch_build")
    assert batch_step["args"][-1] == 2

    steps_ntfc_only = build_test_steps(
        tmp_path,
        "config.txt",
        "build",
        "tests",
        60,
        None,
        True,
        False,
        skip_ntfc=False,
        ntfc_list="ntfc/manifest-host.yaml",
        ntfc_only=True,
    )
    enabled = {s["name"]: s["enabled"] for s in steps_ntfc_only}
    assert enabled["format_check"] is False
    assert enabled["cppcheck"] is False
    assert enabled["batch_build"] is False
    assert enabled["simulator_tests"] is False
    assert enabled["build_size_analysis"] is False
    assert enabled["ntfc_tox"] is True
    assert enabled["ntfc_tests"] is True

    steps_skip_ntfc = build_test_steps(
        tmp_path,
        "config.txt",
        "build",
        "tests",
        60,
        None,
        True,
        False,
        skip_ntfc=True,
    )
    enabled_skip = {s["name"]: s["enabled"] for s in steps_skip_ntfc}
    assert enabled_skip["ntfc_tox"] is False
    assert enabled_skip["ntfc_tests"] is False
    assert enabled_skip["batch_build"] is True

    steps_size_only = build_test_steps(
        tmp_path,
        "config.txt",
        "build",
        "tests",
        60,
        1,
        True,
        False,
        skip_ntfc=False,
        ntfc_list="ntfc/manifest-host.yaml",
        ntfc_only=False,
        size_only=True,
    )
    enabled_size_only = {s["name"]: s["enabled"] for s in steps_size_only}
    assert enabled_size_only["format_check"] is False
    assert enabled_size_only["cppcheck"] is False
    assert enabled_size_only["batch_build"] is True
    assert enabled_size_only["simulator_tests"] is False
    assert enabled_size_only["build_size_analysis"] is True
    size_batch_step = next(
        s for s in steps_size_only if s["name"] == "batch_build"
    )
    assert size_batch_step["args"][-1] == 1


def test_run_format_check(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    project_root = tmp_path / "root"
    project_root.mkdir()
    assert run_format_check(project_root, verbose=False) is False

    script = project_root / "tools" / "scripts" / "check-format.sh"
    script.parent.mkdir(parents=True)
    script.write_text("#!/bin/sh\n", encoding="utf-8")

    monkeypatch.setattr(
        subprocess,
        "run",
        lambda *a, **k: subprocess.CompletedProcess(a[0], 0, "out", "err"),
    )
    assert run_format_check(project_root, verbose=True) is True

    monkeypatch.setattr(
        subprocess,
        "run",
        lambda *a, **k: subprocess.CompletedProcess(a[0], 1, "", ""),
    )
    assert run_format_check(project_root, verbose=False) is False

    def run_boom(*args, **kwargs):
        raise RuntimeError("boom")

    monkeypatch.setattr(subprocess, "run", run_boom)
    assert run_format_check(project_root, verbose=False) is False


def test_run_cppcheck(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    project_root = tmp_path / "root"
    project_root.mkdir()
    assert run_cppcheck(project_root, verbose=False) is False

    script = project_root / "tools" / "scripts" / "cppcheck.sh"
    script.parent.mkdir(parents=True)
    script.write_text("#!/bin/sh\n", encoding="utf-8")

    monkeypatch.setattr(
        subprocess,
        "run",
        lambda *a, **k: subprocess.CompletedProcess(a[0], 0, "out", "err"),
    )
    assert run_cppcheck(project_root, verbose=True) is True

    monkeypatch.setattr(
        subprocess,
        "run",
        lambda *a, **k: subprocess.CompletedProcess(a[0], 1, "", ""),
    )
    assert run_cppcheck(project_root, verbose=False) is False

    def run_boom(*args, **kwargs):
        raise RuntimeError("boom")

    monkeypatch.setattr(subprocess, "run", run_boom)
    assert run_cppcheck(project_root, verbose=False) is False


def test_run_batch_build(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    project_root = tmp_path / "root"
    project_root.mkdir()

    captured = {}

    def run_capture(cmd, **kwargs):
        captured["cmd"] = cmd
        return subprocess.CompletedProcess(cmd, 0)

    monkeypatch.setattr(subprocess, "run", run_capture)
    assert (
        run_batch_build("config.txt", project_root, verbose=True, jobs=2)
        is True
    )
    assert "-v" in captured["cmd"]
    assert "--build-root" in captured["cmd"]
    assert "-j" in captured["cmd"]
    assert "2" in captured["cmd"]

    monkeypatch.setattr(
        subprocess,
        "run",
        lambda *a, **k: subprocess.CompletedProcess(a[0], 1),
    )
    assert run_batch_build("config.txt", project_root, verbose=False) is False

    def run_boom(*args, **kwargs):
        raise RuntimeError("boom")

    monkeypatch.setattr(subprocess, "run", run_boom)
    assert run_batch_build("config.txt", project_root, verbose=False) is False


def test_run_batch_build_if_missing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, patch_project_resolve
) -> None:
    project_root = tmp_path / "root"
    project_root.mkdir()
    patch_project_resolve(project_root)

    config_file = project_root / "config.txt"
    config_file.write_text(
        "boards/sim/sim/sim/configs/nsh_tests\n"
        "boards/arm/some/board/configs/default\n",
        encoding="utf-8",
    )

    build_root = project_root / "build"
    build_root.mkdir()

    def fake_run_batch_build(*args, **kwargs):
        return True

    monkeypatch.setattr(
        "dawnpy_tests.dawn.test_utils.run_batch_build", fake_run_batch_build
    )

    assert (
        run_batch_build_if_missing(
            "config.txt", project_root, verbose=False, build_root="build"
        )
        is True
    )

    sim_dir = build_root / "build-sim-sim-nsh-tests"
    arm_dir = build_root / "build-arm-board-default"
    sim_dir.mkdir(parents=True)
    arm_dir.mkdir(parents=True)
    (sim_dir / "nuttx").write_text("", encoding="utf-8")
    (arm_dir / "nuttx").write_text("", encoding="utf-8")

    monkeypatch.setattr(
        "dawnpy_tests.dawn.test_utils.run_batch_build",
        lambda *a, **k: False,
    )
    assert (
        run_batch_build_if_missing(
            "config.txt", project_root, verbose=False, build_root="build"
        )
        is True
    )


def test_run_batch_build_if_missing_parse_errors(tmp_path: Path) -> None:
    project_root = tmp_path / "root"
    project_root.mkdir()

    assert (
        run_batch_build_if_missing(
            "missing.txt", project_root, verbose=False, build_root="build"
        )
        is False
    )

    bad_config = project_root / "bad.txt"
    bad_config.write_text('"unterminated\n', encoding="utf-8")
    assert (
        run_batch_build_if_missing(
            "bad.txt", project_root, verbose=False, build_root="build"
        )
        is False
    )


def test_run_batch_build_if_missing_ignores_comments_and_blank(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, patch_project_resolve
) -> None:
    project_root = tmp_path / "root"
    project_root.mkdir()
    patch_project_resolve(project_root)

    config_file = project_root / "config.txt"
    config_file.write_text(
        "\n" "# comment\n" "boards/sim/sim/sim/configs/nsh_tests\n",
        encoding="utf-8",
    )

    build_root = project_root / "build"
    sim_dir = build_root / "build-sim-sim-nsh-tests"
    sim_dir.mkdir(parents=True)
    (sim_dir / "nuttx").write_text("", encoding="utf-8")

    monkeypatch.setattr(
        "dawnpy_tests.dawn.test_utils.run_batch_build",
        lambda *a, **k: False,
    )
    assert (
        run_batch_build_if_missing(
            "config.txt", project_root, verbose=False, build_root="build"
        )
        is True
    )


def test_run_ntfc_tests_runs_manifest_sessions_individually(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, patch_project_resolve
) -> None:
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
    (manifest.parent / "requirements.txt").write_text("", encoding="utf-8")
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
    stale_build = root / "build" / "product-demo-main"
    stale_include = stale_build / "include" / "nuttx"
    stale_include.mkdir(parents=True)
    for stale_file in (
        stale_build / ".config",
        stale_build / ".config.orig",
        stale_build / ".config.prev",
        stale_include / "config.h",
    ):
        stale_file.write_text("stale\n", encoding="utf-8")

    captured: list[list[str]] = []
    monkeypatch.chdir(root)
    monkeypatch.setattr(
        "dawnpy_tests.dawn.test_utils.check_ntfc_requirements",
        lambda *a, **k: True,
    )

    def fake_run_stream(cmd, **kwargs):
        captured.append(cmd)
        return True

    monkeypatch.setattr(
        "dawnpy_tests.dawn.test_utils.run_stream",
        fake_run_stream,
    )

    assert run_ntfc_tests(root, manifest, verbose=True) is True
    assert len(captured) == 1
    assert "--rebuild" in captured[0]
    assert "--flash" in captured[0]
    assert not any(arg.startswith("--manifest=") for arg in captured[0])
    assert any(arg.startswith("--confpath=") for arg in captured[0])
    assert any(arg.startswith("--testpath=") for arg in captured[0])
    assert not (stale_build / ".config").exists()
    assert not (stale_build / ".config.orig").exists()
    assert not (stale_build / ".config.prev").exists()
    assert not (stale_include / "config.h").exists()


def test_get_arm_binary_size(monkeypatch: pytest.MonkeyPatch) -> None:
    def run_ok(*args, **kwargs):
        return subprocess.CompletedProcess(
            args[0],
            0,
            ".text 10\n.data 2\n.bss 3\n",
            "",
        )

    monkeypatch.setattr(subprocess, "run", run_ok)
    info = get_arm_binary_size(Path("nuttx"))
    assert info["text"] == 10
    assert info["data"] == 2
    assert info["bss"] == 3
    assert info["total_sram"] == 5

    monkeypatch.setattr(
        subprocess, "run", lambda *a, **k: subprocess.CompletedProcess(a[0], 1)
    )
    info = get_arm_binary_size(Path("nuttx"))
    assert info["error"]

    def run_missing(*args, **kwargs):
        raise FileNotFoundError

    monkeypatch.setattr(subprocess, "run", run_missing)
    info = get_arm_binary_size(Path("nuttx"))
    assert info["error"]

    def run_boom(*args, **kwargs):
        raise RuntimeError("boom")

    monkeypatch.setattr(subprocess, "run", run_boom)
    info = get_arm_binary_size(Path("nuttx"))
    assert info["error"]


def test_analyze_build_sizes(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    missing = tmp_path / "missing"
    assert analyze_build_sizes(missing, tmp_path, verbose=False) is True

    build_root = tmp_path / "build"
    build_root.mkdir()
    assert analyze_build_sizes(build_root, tmp_path, verbose=True) is True

    arm_dir = build_root / "build-arm-test"
    arm_dir.mkdir()
    (arm_dir / "nuttx").write_text("bin", encoding="utf-8")

    def size_ok(binary_path: Path):
        return {
            "text": 1,
            "data": 2,
            "bss": 3,
            "total_sram": 5,
            "error": None,
        }

    def size_err(binary_path: Path):
        return {
            "text": 0,
            "data": 0,
            "bss": 0,
            "total_sram": 0,
            "error": "missing",
        }

    monkeypatch.setattr(
        "dawnpy_tests.dawn.test_utils.get_arm_binary_size", size_err
    )
    assert analyze_build_sizes(build_root, tmp_path, verbose=False) is True

    monkeypatch.setattr(
        "dawnpy_tests.dawn.test_utils.get_arm_binary_size", size_ok
    )
    assert analyze_build_sizes(build_root, tmp_path, verbose=False) is True

    def iterdir_boom(self):
        raise RuntimeError("boom")

    monkeypatch.setattr(Path, "iterdir", iterdir_boom)
    assert analyze_build_sizes(build_root, tmp_path, verbose=False) is True


class FakeStream:
    def __init__(self, lines: list[str]):
        self._lines = lines

    def readline(self) -> str:
        if self._lines:
            return self._lines.pop(0)
        return ""


class FakeProcess:
    def __init__(
        self,
        lines: list[str],
        returncode: int,
        communicate_raises: bool = False,
        wait_raises: bool = False,
    ):
        self._lines = list(lines)
        self.returncode = returncode
        self.stdout = FakeStream(self._lines)
        self.stderr = FakeStream([])
        self._terminated = False
        self._communicate_raises = communicate_raises
        self._wait_raises = wait_raises

    def poll(self) -> int | None:  # pragma: no cover
        if self._terminated:
            return self.returncode
        if self._lines:
            return None
        return self.returncode

    def terminate(self) -> None:
        self._terminated = True

    def wait(self, timeout: int | None = None) -> int:
        if self._wait_raises:
            raise subprocess.TimeoutExpired("wait", timeout=timeout)
        return self.returncode

    def kill(self) -> None:
        self._terminated = True

    def communicate(self, timeout: int | None = None) -> tuple[str, str]:
        if self._communicate_raises:
            raise subprocess.TimeoutExpired("comm", timeout=timeout)
        return ("", "")


class RaisingStream:
    def readline(self) -> str:
        raise RuntimeError("boom")


class RaisingProcess(FakeProcess):
    def __init__(self, returncode: int):
        super().__init__([], returncode)
        self.stdout = RaisingStream()
        self.stderr = FakeStream([])
        self._polls = 0

    def poll(self) -> int | None:
        if self._polls == 0:
            self._polls += 1
            return None
        return self.returncode


def test_run_simulator_tests_success(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    build_dir = tmp_path / "build"
    build_dir.mkdir()
    (build_dir / "nuttx").write_text("bin", encoding="utf-8")

    monkeypatch.setattr(
        subprocess,
        "Popen",
        lambda *a, **k: FakeProcess(["hello\n"], 0),
    )
    assert run_simulator_tests(build_dir, tmp_path, timeout=1) is True


def test_run_simulator_tests_assertion_failure(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    build_dir = tmp_path / "build"
    build_dir.mkdir()
    (build_dir / "nuttx").write_text("bin", encoding="utf-8")

    monkeypatch.setattr(
        subprocess,
        "Popen",
        lambda *a, **k: FakeProcess(
            ["dump_assert_info: Assertion failed\n"], 1, wait_raises=True
        ),
    )
    assert run_simulator_tests(build_dir, tmp_path, timeout=1) is False


def test_run_simulator_tests_timeout(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    build_dir = tmp_path / "build"
    build_dir.mkdir()
    (build_dir / "nuttx").write_text("bin", encoding="utf-8")

    monkeypatch.setattr(
        subprocess,
        "Popen",
        lambda *a, **k: FakeProcess(["hello\n"], 0, communicate_raises=True),
    )
    assert run_simulator_tests(build_dir, tmp_path, timeout=1) is False


def test_run_simulator_tests_failure(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    build_dir = tmp_path / "build"
    build_dir.mkdir()
    (build_dir / "nuttx").write_text("bin", encoding="utf-8")

    monkeypatch.setattr(
        subprocess, "Popen", lambda *a, **k: FakeProcess(["ok\n"], 1)
    )
    assert run_simulator_tests(build_dir, tmp_path, timeout=1) is False


def test_run_simulator_tests_exception(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    build_dir = tmp_path / "build"
    build_dir.mkdir()
    (build_dir / "nuttx").write_text("bin", encoding="utf-8")

    def raise_boom(*args, **kwargs):
        raise RuntimeError("boom")

    monkeypatch.setattr(subprocess, "Popen", raise_boom)
    assert run_simulator_tests(build_dir, tmp_path, timeout=1) is False


def test_run_simulator_tests_read_error(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    build_dir = tmp_path / "build"
    build_dir.mkdir()
    (build_dir / "nuttx").write_text("bin", encoding="utf-8")

    monkeypatch.setattr(subprocess, "Popen", lambda *a, **k: RaisingProcess(0))
    assert run_simulator_tests(build_dir, tmp_path, timeout=1) is True


def test_run_simulator_tests_missing_binary(tmp_path: Path) -> None:
    build_dir = tmp_path / "build"
    build_dir.mkdir()
    assert run_simulator_tests(build_dir, tmp_path, timeout=1) is False


def test_emit_remaining_output() -> None:
    class OutputProcess(FakeProcess):
        def communicate(self, timeout: int | None = None) -> tuple[str, str]:
            return ("out", "err")

    _emit_remaining_output(OutputProcess([], 0))


def test_fake_stream_and_process() -> None:
    stream = FakeStream([])
    assert stream.readline() == ""

    proc = FakeProcess([], 0)
    proc._terminated = True
    assert proc.poll() == 0
    assert proc.wait() == 0


def test_dawnpy_env(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    project_root = tmp_path / "root"
    dawnpy_src = project_root / "tools" / "dawnpy" / "src"
    dawnpy_src.mkdir(parents=True)

    monkeypatch.setenv("PYTHONPATH", "existing")
    env = _dawnpy_env(project_root)
    assert "PYTHONPATH" in env
    assert "existing" in env["PYTHONPATH"]
