"""Standalone CLI entry point for dawnpy-tests."""

from dawnpy_tests.commands.cmd_test import cmd_test


def main() -> None:
    """Run the Dawn QA CLI."""
    cmd_test(prog_name="dawnpy-tests")


if __name__ == "__main__":
    main()
