# dawnpy-tests

QA and test orchestration package for Dawn.

Main Dawn project: [railab/dawn](https://github.com/railab/dawn).

This distribution depends on the core `dawnpy` package plus all transport
extensions:

- `dawnpy-serial`
- `dawnpy-can`
- `dawnpy-udp`
- `dawnpy-modbus`

It exposes the standalone `dawnpy-tests` CLI and keeps the QA runner aligned
with the full communication feature surface used by integration and system
tests.
