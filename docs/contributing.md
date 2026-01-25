# Contributing to Jobify

Thank you for your interest in contributing to Jobify! We are always looking for new contributors.

## Getting Started

To start contributing, you will need to set up a development environment.

### Prerequisites

- **[uv](https://github.com/astral-sh/uv)**: A fast and efficient Python package and project manager.
- **[Just](https://github.com/casey/just):** A handy command-line tool used for various development tasks.

### Setup

Once you have installed the necessary prerequisites, run the following command to set up your environment:

```bash
just init
```

This command will:

1. Synchronize the project dependencies using `uv`.
2. Install the `pre-commit` hooks.

## Development Workflow

1. Fork the repository and create your own branch from the `main` branch.
2. Make your desired changes to the code.
3. Ensure code quality by running the linter and static analysis tools.
4. Write and run tests to verify the changes.
5. Submit a Pull Request for review.

### Code Quality

We use several tools to ensure high code quality. You can run all of them using the `just` command:

- **Linter**: Runs Ruff (format and check) and Codespell.
  ```bash
  just linter
  ```
- **Static Analysis**: Runs Mypy, Basedpyright, Bandit, Semgrep, and Zizmor.
  ```bash
  just static-analysis
  ```
- **Pre-commit**: It's recommended to run pre-commit on all files before pushing.
  ```bash
  just pre-commit-all
  ```

### Testing

Always add tests for new features or bug fixes. We use `pytest` for testing.

- **Run all tests**:
  ```bash
  just test-all
  ```
- **Run tests with coverage**:
  ```bash
  just test-coverage-all
  ```

## Pull Request Guidelines

- Make sure your code follows the project's coding style (Ruff).
- Keep your pull requests focused. If you have multiple changes that are unrelated, please create separate pull requests.
- If you are adding or changing a feature, update the relevant documentation.
- All pull requests must pass the continuous integration tests before they can be merged.

## Commit Messages

We follow the [Conventional Commits](https://www.conventionalcommits.org/) for our commit messages. This helps in generating changelogs and managing releases automatically.

Format: `<type>(<scope>): <description>`

Example types:

- `feat`: A new feature
- `fix`: A bug fix
- `docs`: Documentation only changes
- `style`: Changes that do not affect the meaning of the code (white-space, formatting, etc)
- `refactor`: A code change that neither fixes a bug nor adds a feature
- `perf`: A code change that improves performance
- `test`: Adding missing tests or correcting existing tests
- `chore`: Changes to the build process or auxiliary tools and libraries
