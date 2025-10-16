# Cross-platform shell configuration
# Use PowerShell on Windows (higher precedence than shell setting)
set windows-shell := ["powershell.exe", "-NoLogo", "-Command"]
# Use sh on Unix-like systems
set shell := ["sh", "-c"]

[private]
default:
  @just --list --unsorted --list-heading $'commands…\n'

[doc("Prepare venv and repo for developing")]
[group("Common")]
init:
  uv sync --group dev


[doc("Install pre-commit hooks")]
[group("pre-commit")]
pre-commit-install:
  uv run --active --frozen pre-commit install

[doc("Pre-commit all files")]
[group("pre-commit")]
pre-commit-all:
  uv run --active --frozen pre-commit run --show-diff-on-failure --color=always --all-files


# Linter
_linter *params:
  uv run --no-dev --group lint --active --frozen {{params}}

[doc("Ruff format")]
[group("linter")]
ruff-format *params:
  just _linter ruff format {{params}}

[doc("Ruff check")]
[group("linter")]
ruff-check *params:
  just _linter ruff check --exit-non-zero-on-fix {{params}}

_codespell:
  just _linter codespell

[doc("Check typos")]
[group("linter")]
typos: _codespell
  just _linter pre-commit run --all-files typos

[doc("Linter run")]
[group("linter")]
linter: ruff-format ruff-check _codespell


# Static analysis
_static-analysis *params:
  uv run --no-dev --group lint --active --frozen {{params}}

[doc("Mypy check")]
[group("static analysis")]
mypy *params:
  just _static-analysis mypy {{params}}

[doc("Basedpyright check")]
[group("static analysis")]
basedpyright *params:
  just _static-analysis basedpyright --warnings --project pyproject.toml {{params}}

[doc("Bandit check")]
[group("static analysis")]
bandit:
  just _static-analysis bandit -c pyproject.toml -r src

[doc("Semgrep check")]
[group("static analysis")]
semgrep:
  just _static-analysis semgrep scan --config auto --error src

[doc("Zizmor check")]
[group("static analysis")]
zizmor:
  just _static-analysis zizmor .

[doc("Static analysis check")]
[group("static analysis")]
static-analysis: mypy basedpyright bandit semgrep


# Tests
_test *params:
  uv run --no-dev --group test --active --frozen pytest {{params}}

[doc("Run all tests")]
[group("tests")]
test-all +param="tests/":
  just _test {{param}}

[doc("Run all tests with coverage")]
[group("tests")]
test-coverage-all +param="tests/":
  just _test {{param}} --cov --cov-report=term:skip-covered
