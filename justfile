# Cross-platform shell configuration
# Use PowerShell on Windows (higher precedence than shell setting)
set windows-shell := ["powershell.exe", "-NoLogo", "-Command"]
# Use sh on Unix-like systems
set shell := ["sh", "-c"]


[doc("All command information")]
[group("Common")]
[private]
default:
  @just --list --unsorted --list-heading $'commands…\n'


[doc("Prepare venv and repo for developing")]
[group("Common")]
bootstrap:
    just venv-sync-dev
    pre-commit install


[doc("Sync latest versions of packages")]
[group("Common")]
venv-sync-dev:
    uv pip install -e . --group dev


[doc("Lint check")]
[group("Linter and Static")]
lint:
    echo "Run ruff check..." && ruff check --exit-non-zero-on-fix
    echo "Run ruff format..." && ruff format
    echo "Run codespell..." && codespell


[doc("Static analysis")]
[group("Linter and Static")]
static:
    echo "Run mypy.." && mypy --config-file pyproject.toml
    echo "Run bandit..." && bandit -c pyproject.toml -r src
    echo "Run semgrep..." && semgrep scan --config auto --error
    uv run --active --frozen basedpyright --warnings --project pyproject.toml


[doc("Run pre-commit all files")]
[group("Linter and Static")]
pre-commit:
    pre-commit run --show-diff-on-failure --color=always --all-files


[doc("Run test")]
[group("Test")]
test *args:
    coverage run -m pytest -x --ff {{ args }}


[doc("Run test with coverage")]
[group("Test")]
test-cov *args:
    just test {{ args }}
    coverage combine
    coverage report --show-missing --skip-covered --sort=cover --precision=2
    rm .coverage*
