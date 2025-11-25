# Cross-platform shell configuration
# Use PowerShell on Windows (higher precedence than shell setting)
set windows-shell := ["powershell.exe", "-NoLogo", "-Command"]
# Use sh on Unix-like systems
set shell := ["sh", "-c"]

export VIRTUAL_ENV := ".venv"

[private]
default:
  @just --list --unsorted --list-heading $'commands…\n'

[doc("Prepare venv and repo for developing")]
[group("Common")]
init:
  uv sync --group dev


# Pre-commit
[doc("Install pre-commit hooks")]
[group("pre-commit")]
_pre-commit *params:
  uv run --frozen pre-commit {{params}}

pre-commit-install:
  just _pre-commit install

[doc("Pre-commit all files")]
[group("pre-commit")]
pre-commit-all:
  just _pre-commit run --show-diff-on-failure --color=always --all-files


# Linter
_setup_lint *params:
  uv run --no-dev --group lint --frozen {{params}}

[doc("Ruff format")]
[group("linter")]
ruff-format *params:
  just _setup_lint ruff format {{params}}

[doc("Ruff check")]
[group("linter")]
ruff-check *params:
  just _setup_lint ruff check --exit-non-zero-on-fix {{params}}

_codespell:
  just _setup_lint codespell

[doc("Check typos")]
[group("linter")]
typos: _codespell
  just _setup_lint pre-commit run --all-files typos

[doc("Linter run")]
[group("linter")]
linter: ruff-format ruff-check _codespell


# Static analysis
_setup_static *params:
  uv run --frozen {{params}}

[doc("Mypy check")]
[group("static analysis")]
mypy *params:
  just _setup_static mypy {{params}}

[doc("Basedpyright check")]
[group("static analysis")]
basedpyright *params:
  just _setup_static basedpyright --warnings --project pyproject.toml {{params}}

[doc("Bandit check")]
[group("static analysis")]
bandit:
  just _setup_static bandit -c pyproject.toml -r src

[doc("Semgrep check")]
[group("static analysis")]
semgrep:
  just _setup_static semgrep scan --config auto --error src

[doc("Zizmor check")]
[group("static analysis")]
zizmor:
  just _setup_static zizmor .

[doc("Static analysis check")]
[group("static analysis")]
static-analysis: mypy basedpyright bandit semgrep


# Tests
_setup_test *params:
  uv run --no-dev --group test --frozen pytest {{params}}

[doc("Run all tests")]
[group("tests")]
test-all +param="tests/":
  just _setup_test {{param}}

[doc("Run all tests with coverage")]
[group("tests")]
test-coverage-all +param="tests/":
  just _setup_test {{param}} --cov --cov-report=term:skip-covered
