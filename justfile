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
[doc("Ruff format")]
[group("linter")]
ruff-format *params:
  uv run --active --frozen ruff format {{params}}

[doc("Ruff check")]
[group("linter")]
ruff-check *params:
  uv run --active --frozen ruff check --exit-non-zero-on-fix {{params}}

_codespell:
  uv run --active --frozen codespell

[doc("Check typos")]
[group("linter")]
typos: _codespell
  uv run --active --frozen pre-commit run --all-files typos

[doc("Linter run")]
[group("linter")]
linter: ruff-format ruff-check _codespell


# Static analysis
[doc("Mypy check")]
[group("static analysis")]
mypy *params:
  uv run --active --frozen mypy {{params}}

[doc("Basedpyright check")]
[group("static analysis")]
basedpyright *params:
  uv run --active --frozen basedpyright --warnings --project pyproject.toml

[doc("Bandit check")]
[group("static analysis")]
bandit:
  uv run --active --frozen bandit -c pyproject.toml -r src

[doc("Semgrep check")]
[group("static analysis")]
semgrep:
  uv run --active --frozen semgrep scan --config auto --error src

[doc("Zizmor check")]
[group("static analysis")]
zizmor:
  uv run --active --frozen zizmor .

[doc("Static analysis check")]
[group("static analysis")]
static-analysis: mypy basedpyright bandit semgrep
