# tools/dawnpy-tests/src/dawnpy_tests/dawn/test_utils.py
#
# SPDX-License-Identifier: Apache-2.0
#

"""Test and analysis helpers for Dawn tooling."""

import os
import shlex
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import TypedDict

import click
import yaml
from dawnpy.dawn.build_dir import generate_build_dir_name
from dawnpy.dawn.output import (
    colored,
    print_error,
    print_info,
    print_success,
    print_verbose,
    print_warning,
)
from dawnpy.dawn.proc import run_capture_echo, run_stream
from dawnpy.dawn.project import Project


class ArmSizeInfo(TypedDict):
    """Size details parsed from arm-none-eabi-size output."""

    text: int
    data: int
    bss: int
    total_sram: int
    error: str | None


class ArmBuildInfo(TypedDict):
    """Summary of an ARM build directory and its size info."""

    name: str
    size_info: ArmSizeInfo


def _parse_arm_sizes(output: str) -> tuple[int, int, int]:
    sizes = {"text": 0, "data": 0, "bss": 0}
    for line in output.split("\n"):
        parts = line.strip().split()
        if len(parts) < 2:
            continue
        section = parts[0]
        if section == ".text":
            sizes["text"] = int(parts[1])
        elif section == ".data":
            sizes["data"] = int(parts[1])
        elif section == ".bss":
            sizes["bss"] = int(parts[1])
    return sizes["text"], sizes["data"], sizes["bss"]


def _dawnpy_env(project_root: Path) -> dict[str, str]:
    env = os.environ.copy()
    dawnpy_src = project_root / "tools" / "dawnpy" / "src"
    if dawnpy_src.exists():
        existing = env.get("PYTHONPATH", "")
        env["PYTHONPATH"] = (
            f"{dawnpy_src}:{existing}" if existing else str(dawnpy_src)
        )
    return env


def run_format_check(project_root: Path, verbose: bool) -> bool:
    """Run code format check and fix."""
    print_info("Step 0: Running code format check and fix...")
    click.echo()

    script_path = project_root / "tools" / "scripts" / "check-format.sh"

    if not script_path.exists():
        print_error(f"Format check script not found: {script_path}")
        return False

    print_verbose(f"Running: {script_path} fix", verbose=True)

    if not run_capture_echo(
        [str(script_path), "fix"],
        cwd=project_root,
        error_message="Format check failed",
    ):
        return False

    print_success("Code format check and fix completed successfully")
    return True


def run_cppcheck(project_root: Path, verbose: bool) -> bool:
    """Run cppcheck static analysis."""
    print_info("Step 0b: Running cppcheck static analysis...")
    click.echo()

    script_path = project_root / "tools" / "scripts" / "cppcheck.sh"

    if not script_path.exists():
        print_error(f"cppcheck script not found: {script_path}")
        return False

    print_verbose(f"Running: {script_path}", verbose=True)

    if not run_capture_echo(
        [str(script_path)],
        cwd=project_root,
        error_message="cppcheck failed",
    ):
        return False

    print_success("cppcheck completed successfully")
    return True


def run_ntfc_tox(project_root: Path, verbose: bool) -> bool:
    """Run ntfc/tox.ini checks (format + flake8)."""
    print_info("Running ntfc tox checks...")
    click.echo()

    ntfc_dir = project_root / "ntfc"
    tox_ini = ntfc_dir / "tox.ini"

    if not tox_ini.exists():
        print_error(f"ntfc tox.ini not found: {tox_ini}")
        return False

    print_verbose(f"Running: tox -c {tox_ini}", verbose=True)

    if not run_capture_echo(
        ["tox", "-c", str(tox_ini)],
        cwd=ntfc_dir,
        error_message="ntfc tox checks failed",
    ):
        return False

    print_success("ntfc tox checks completed successfully")
    return True


def run_batch_build(
    config_file: str,
    project_root: Path,
    verbose: bool,
    build_root: str = "build",
    jobs: int | None = None,
) -> bool:
    """Run batch build with all configurations."""
    print_info("Step 1: Building all configurations...")
    click.echo()

    cmd = [sys.executable, "-m", "dawnpy", "batch", config_file]
    cmd.extend(["--build-root", build_root])
    if jobs is not None:
        cmd.extend(["-j", str(jobs)])

    if verbose:
        cmd.append("-v")

    if not run_stream(
        cmd,
        cwd=project_root,
        env=_dawnpy_env(project_root),
        error_message="Batch build failed",
    ):
        return False

    print_success("All configurations built successfully")
    return True


def _parse_batch_confpaths(config_file_path: Path) -> list[str] | None:
    """Parse batch config file and return configuration paths."""
    try:
        lines = config_file_path.read_text(encoding="utf-8").splitlines()
    except Exception as e:
        print_error(f"Failed to read batch config file: {e}")
        return None

    confpaths: list[str] = []
    for raw in lines:
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        try:
            parts = shlex.split(line)
        except ValueError as e:
            print_error(f"Invalid batch config line: {raw} ({e})")
            return None
        confpaths.append(parts[0])

    return confpaths


def run_batch_build_if_missing(
    config_file: str,
    project_root: Path,
    verbose: bool,
    build_root: str = "build",
    jobs: int | None = None,
) -> bool:
    """Build only configurations missing build artifacts."""
    print_info("Step 1: Ensuring build configurations for size analysis...")
    click.echo()

    config_path = (project_root / config_file).resolve()
    confpaths = _parse_batch_confpaths(config_path)
    if confpaths is None:
        return False

    build_root_path = project_root / build_root
    missing: list[str] = []
    for confpath in confpaths:
        resolved_confpath = confpath
        candidate = (config_path.parent / confpath).resolve()
        if candidate.exists():
            resolved_confpath = str(candidate)
        project = Project.resolve(Path(resolved_confpath))
        build_dir = build_root_path / generate_build_dir_name(
            resolved_confpath,
            project_root=project.project_root,
            dawn_root=project.dawn_root,
        )
        if not (build_dir / "nuttx").exists():
            missing.append(confpath)

    if not missing:
        print_success("All build configurations are present")
        return True

    print_info(
        f"Missing build artifacts for {len(missing)} configuration(s), "
        "running batch build"
    )
    return run_batch_build(
        config_file, project_root, verbose, build_root, jobs
    )


def _parse_requirement_name(line: str) -> str | None:
    """Extract bare distribution name from one requirements.txt line.

    Returns None for blank/comment lines. Strips version specifiers,
    extras, and environment markers so the name can be fed to
    importlib.metadata.
    """
    stripped = line.split("#", 1)[0].strip()
    if not stripped:
        return None
    if stripped.startswith("-"):
        return None
    token = stripped.split(";", 1)[0].strip()
    for sep in ("==", ">=", "<=", "~=", "!=", ">", "<"):
        if sep in token:
            token = token.split(sep, 1)[0].strip()
            break
    token = token.split("[", 1)[0].strip()
    return token or None


def check_ntfc_requirements(
    project_root: Path, requirements_path: Path, verbose: bool = False
) -> bool:
    """Verify every package listed in an NTFC requirements file is installed.

    Reports all missing distributions in a single message so users can
    install them in one step.
    """
    from importlib.metadata import PackageNotFoundError, version

    if not requirements_path.exists():
        print_warning(f"NTFC requirements file not found: {requirements_path}")
        return True

    missing: list[str] = []
    for raw in requirements_path.read_text(encoding="utf-8").splitlines():
        name = _parse_requirement_name(raw)
        if name is None:
            continue
        try:
            version(name)
        except PackageNotFoundError:
            missing.append(name)

    if missing:
        print_error(
            "NTFC host-side dependencies missing: " + ", ".join(missing)
        )
        rel = requirements_path.relative_to(project_root)
        print_info(f"Install with: pip install -r {rel}")
        return False

    print_verbose("NTFC host-side dependencies satisfied", verbose)
    return True


def _merge_build_env(
    base_env: dict[str, str], extra_env: dict[str, str] | None
) -> dict[str, str]:
    merged = dict(base_env)
    if extra_env:
        merged.update(
            {str(key): str(value) for key, value in extra_env.items()}
        )
    return merged


def _resolve_first_existing(value: str, *base_dirs: Path) -> str:
    path = Path(value)
    if path.is_absolute():
        return str(path)

    for base_dir in base_dirs:
        candidate = (base_dir / path).resolve()
        if candidate.exists():
            return str(candidate)

    if base_dirs:
        return str((base_dirs[0] / path).resolve())
    return str(path.resolve())


def _normalize_ntfc_config(config_path: Path, temp_root: Path) -> Path:
    config_dir = config_path.parent
    with config_path.open(encoding="utf-8") as handle:
        config = yaml.safe_load(handle) or {}

    common = config.setdefault("config", {})
    config_cwd = common.get("cwd", ".")
    project_root = Project.resolve(config_path).project_root
    cwd_path = _resolve_first_existing(
        str(config_cwd), project_root, config_dir
    )
    common["cwd"] = cwd_path

    build_dir = common.get("build_dir", "./build")
    common["build_dir"] = _resolve_first_existing(
        str(build_dir), project_root, config_dir, Path(cwd_path)
    )

    common["build_env"] = _merge_build_env(
        Project.resolve().cmake_env(),
        (
            common.get("build_env")
            if isinstance(common.get("build_env"), dict)
            else None
        ),
    )

    for key, product in config.items():
        if "product" not in key or not isinstance(product, dict):
            continue
        cores = product.get("cores", {})
        if not isinstance(cores, dict):
            continue
        for core in cores.values():
            if not isinstance(core, dict) or "defconfig" not in core:
                continue
            defconfig_path = Path(
                _resolve_first_existing(
                    str(core["defconfig"]),
                    Path(cwd_path) / "nuttx",
                    project_root,
                    config_dir,
                )
            )
            project = Project.resolve(defconfig_path)
            core["defconfig"] = str(defconfig_path)
            core["build_env"] = _merge_build_env(
                project.cmake_env(),
                (
                    core["build_env"]
                    if isinstance(core.get("build_env"), dict)
                    else None
                ),
            )

    normalized_path = (
        temp_root / f"{config_path.parent.name}-{config_path.name}"
    )
    with normalized_path.open("w", encoding="utf-8") as handle:
        yaml.safe_dump(config, handle, sort_keys=False)
    return normalized_path


def _normalize_ntfc_manifest(manifest_path: Path) -> Path:
    temp_root = Path(
        tempfile.mkdtemp(prefix="dawnpy-tests-ntfc-", dir="/tmp")
    ).resolve()
    with manifest_path.open(encoding="utf-8") as handle:
        manifest = yaml.safe_load(handle) or {}

    sessions = manifest.get("sessions", [])
    if not isinstance(sessions, list):
        raise ValueError("NTFC manifest sessions must be a list")

    manifest_dir = manifest_path.parent
    for session in sessions:
        if not isinstance(session, dict):
            continue
        confpath = session.get("confpath")
        if not isinstance(confpath, str):
            continue
        project_root = Project.resolve(manifest_path).project_root
        config_path = Path(
            _resolve_first_existing(confpath, project_root, manifest_dir)
        )
        session["confpath"] = str(
            _normalize_ntfc_config(config_path, temp_root)
        )
        testpath = session.get("testpath")
        if isinstance(testpath, str):
            session["testpath"] = _resolve_first_existing(
                testpath, project_root, manifest_dir
            )

    normalized_manifest = temp_root / manifest_path.name
    with normalized_manifest.open("w", encoding="utf-8") as handle:
        yaml.safe_dump(manifest, handle, sort_keys=False)
    return normalized_manifest


def _ntfc_product_build_dirs(config_path: Path) -> list[Path]:
    with config_path.open(encoding="utf-8") as handle:
        config = yaml.safe_load(handle) or {}

    common = config.get("config", {})
    build_root = Path(str(common.get("build_dir", "./build")))
    build_dirs: list[Path] = []

    for product_key, product in config.items():
        if "product" not in product_key or not isinstance(product, dict):
            continue
        product_name = product.get("name")
        cores = product.get("cores", {})
        if not isinstance(product_name, str) or not isinstance(cores, dict):
            continue

        for core in cores.values():
            if not isinstance(core, dict) or "defconfig" not in core:
                continue
            core_name = core.get("name")
            if not isinstance(core_name, str):
                continue
            build_dirs.append(
                build_root / f"{product_key}-{product_name}-{core_name}"
            )

    return build_dirs


def _unlink_if_exists(path: Path) -> None:
    try:
        path.unlink()
    except FileNotFoundError:
        return


def _reset_ntfc_build_config(build_dir: Path, verbose: bool = False) -> bool:
    if not build_dir.exists():
        return True

    if (build_dir / "build.ninja").is_file():
        cmd = [
            "cmake",
            "--build",
            str(build_dir),
            "--target",
            "distcleanconfig",
        ]
        result = subprocess.run(
            cmd,
            check=False,
            capture_output=True,
            text=True,
        )
        if result.returncode == 0:
            print_verbose(
                f"Reset NTFC generated config in '{build_dir}'", verbose
            )
            return True

    for path in (
        build_dir / ".config",
        build_dir / ".config.orig",
        build_dir / ".config.prev",
        build_dir / "include" / "nuttx" / "config.h",
    ):
        _unlink_if_exists(path)

    print_verbose(f"Reset NTFC generated config in '{build_dir}'", verbose)
    return True


def _reset_ntfc_session_configs(config_path: Path, verbose: bool) -> bool:
    for build_dir in _ntfc_product_build_dirs(config_path):
        if not _reset_ntfc_build_config(build_dir, verbose):
            return False
    return True


def run_ntfc_tests(
    project_root: Path, manifest_path: Path, verbose: bool = False
) -> bool:
    """Run NTFC test sessions from a manifest YAML file.

    Executes sessions one by one so hardware targets that share one board are
    flashed immediately before their own tests run.
    """
    print_info("Step 3: Running NTFC tests...")
    click.echo()

    if not manifest_path.exists():  # pragma: no cover
        print_error(f"NTFC manifest not found: {manifest_path}")
        return False

    requirements_path = manifest_path.parent / "requirements.txt"
    if not check_ntfc_requirements(project_root, requirements_path, verbose):
        return False

    normalized_manifest = _normalize_ntfc_manifest(manifest_path)
    with normalized_manifest.open(encoding="utf-8") as handle:
        manifest = yaml.safe_load(handle) or {}

    sessions = manifest.get("sessions", [])
    if not isinstance(sessions, list):
        print_error("NTFC manifest sessions must be a list")
        return False

    for session in sessions:
        if not isinstance(session, dict):
            continue
        name = str(session.get("name", "unnamed"))
        confpath = session.get("confpath")
        testpath = session.get("testpath")
        if not isinstance(confpath, str) or not isinstance(testpath, str):
            print_error(f"Invalid NTFC session paths: {name}")
            return False

        if not _reset_ntfc_session_configs(Path(confpath), verbose):
            return False

        cmd = [
            sys.executable,
            "-m",
            "ntfc",
            "test",
            f"--confpath={confpath}",
            f"--testpath={testpath}",
            "--rebuild",
            "--flash",
        ]
        print_verbose(f"Running [{name}]: {' '.join(cmd)}", verbose)

        if not run_stream(
            cmd,
            cwd=project_root,
            env=_dawnpy_env(project_root),
            error_message=f"NTFC session failed: {name}",
        ):  # pragma: no cover
            return False

    print_success("NTFC tests completed successfully")
    return True


def get_arm_binary_size(binary_path: Path) -> ArmSizeInfo:
    """Get detailed size information for ARM binaries."""
    size_info: ArmSizeInfo = {
        "text": 0,
        "data": 0,
        "bss": 0,
        "total_sram": 0,
        "error": None,
    }

    try:
        result = subprocess.run(
            ["arm-none-eabi-size", "-A", str(binary_path)],
            capture_output=True,
            text=True,
            check=False,
        )

        if result.returncode != 0:
            size_info["error"] = "arm-none-eabi-size not available"
            return size_info

        text, data, bss = _parse_arm_sizes(result.stdout)
        size_info["text"] = text
        size_info["data"] = data
        size_info["bss"] = bss
        size_info["total_sram"] = data + bss
        return size_info
    except FileNotFoundError:
        size_info["error"] = "arm-none-eabi-size command not found"
        return size_info
    except Exception as e:
        size_info["error"] = str(e)
        return size_info

    return size_info


def analyze_build_sizes(
    build_root: Path, project_root: Path, verbose: bool = False
) -> bool:
    """Analyze and display memory usage for ARM configurations."""
    print_info("Step 4: Analyzing ARM build memory usage...")
    click.echo()

    if not build_root.exists():
        print_warning(f"Build root directory not found: {build_root}")
        return True

    arm_builds: list[ArmBuildInfo] = []
    try:
        for build_dir in sorted(build_root.iterdir()):
            if build_dir.is_dir() and build_dir.name.startswith("build-arm-"):
                nuttx_binary = build_dir / "nuttx"
                if nuttx_binary.exists():
                    size_info = get_arm_binary_size(nuttx_binary)
                    arm_builds.append(
                        {
                            "name": build_dir.name,
                            "size_info": size_info,
                        }
                    )
    except Exception as e:
        print_warning(f"Failed to scan build directories: {e}")
        return True

    if not arm_builds:
        print_verbose("No ARM build configurations found", verbose)
        return True

    click.echo()
    print_success("ARM Build Memory Usage")
    click.echo()

    for build in arm_builds:
        info = build["size_info"]
        click.echo(colored(build["name"], "blue"))

        if info["error"]:
            click.echo(f"  {colored('[WARN]', 'yellow')} {info['error']}")
        else:
            click.echo(
                f"  .text section:  {info['text']:>10,} bytes "
                f"({info['text'] / 1024.0:>8.1f} KB)  - Program code"
            )
            click.echo(
                f"  .data section:  {info['data']:>10,} bytes "
                f"({info['data'] / 1024.0:>8.1f} KB)  - Initialized data"
            )
            click.echo(
                f"  .bss section:   {info['bss']:>10,} bytes "
                f"({info['bss'] / 1024.0:>8.1f} KB)  - Uninitialized data"
            )
            click.echo(
                f"  Total SRAM:     {info['total_sram']:>10,} bytes "
                f"({info['total_sram'] / 1024.0:>8.1f} KB)  - Runtime memory"
            )

        click.echo()

    return True


def run_simulator_tests(
    build_dir: Path, project_root: Path, timeout: int = 60
) -> bool:
    """Run simulator tests from build directory."""
    print_info("Step 2: Running simulator tests...")
    click.echo()

    nuttx_binary = build_dir / "nuttx"

    if not nuttx_binary.exists():
        print_error(f"Test binary not found: {nuttx_binary}")
        return False

    print_verbose(f"Running: {nuttx_binary}", verbose=True)
    print_verbose(f"Test timeout: {timeout} seconds", verbose=True)

    _print_test_banner("TEST OUTPUT")
    click.echo()

    try:
        process = subprocess.Popen(
            [str(nuttx_binary)],
            cwd=project_root,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            bufsize=1,
        )
        assert process.stdout is not None
        assert process.stderr is not None

        test_failed, failure_reason = _read_test_output(process)
        try:
            _emit_remaining_output(process)
        except subprocess.TimeoutExpired:
            process.kill()
            click.echo()
            _print_test_banner("TEST RESULT")
            print_error(f"Test execution timed out ({timeout} second timeout)")
            print_info(
                "Tests may be taking longer than expected. "
                "Use --test-timeout option to increase the timeout."
            )
            return False

        click.echo()
        click.echo(colored("=" * 60, "blue"))

        if test_failed:
            _print_test_banner("TEST RESULT")
            print_error("Tests failed")
            if failure_reason:
                click.echo(f"Reason: {failure_reason}")
            return False

        if process.returncode == 0:
            _print_test_banner("TEST RESULT")
            print_success("All tests passed")
            return True

        _print_test_banner("TEST RESULT")
        print_error(f"Tests failed with exit code {process.returncode}")
        return False

    except Exception as e:
        print_error(f"Failed to run tests: {e}")
        return False


def _print_test_banner(title: str) -> None:
    bar = colored("=" * 60, "blue")
    click.echo(bar)
    click.echo(colored(title, "blue"))
    click.echo(bar)


def _terminate_process(process: subprocess.Popen[str]) -> None:
    process.terminate()
    try:
        process.wait(timeout=2)
    except subprocess.TimeoutExpired:
        process.kill()


def _read_test_output(  # pragma: no cover
    process: subprocess.Popen[str],
) -> tuple[bool, str | None]:
    test_failed = False
    failure_reason = None

    assert process.stdout is not None
    while True:
        try:
            stdout_line = process.stdout.readline()
        except Exception:
            if process.poll() is not None:
                break
            continue

        if not stdout_line:
            break

        click.echo(stdout_line, nl=False)
        if "dump_assert_info: Assertion failed" in stdout_line:
            test_failed = True
            failure_reason = stdout_line.strip()
            _terminate_process(process)
            break
        if "Test result: FAILED!" in stdout_line:
            test_failed = True
            failure_reason = "Test suite reported failure"
            _terminate_process(process)
            break

    return test_failed, failure_reason


def _emit_remaining_output(process: subprocess.Popen[str]) -> None:
    remaining_stdout, remaining_stderr = process.communicate(timeout=1)
    if remaining_stdout:
        click.echo(remaining_stdout, nl=False)
    if remaining_stderr:
        click.echo(remaining_stderr, err=True, nl=False)
