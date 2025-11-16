# PR Quality Verification Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add automated PR quality verification with GitHub Actions running tests, linting, type checking, and documentation checks.

**Architecture:** Matrix testing across Python 3.11/3.12 + parallel static analysis jobs (ruff, mypy, docs). All jobs use uv, fail on errors, provide clear feedback.

**Tech Stack:** GitHub Actions, pytest, ruff, mypy, uv

---

## Task 1: Add Quality Tools to Dependencies

**Files:**
- Modify: `requirements.txt`

**Step 1: Add ruff and mypy to requirements.txt**

Add these lines to the end of `requirements.txt`:

```
ruff>=0.1.0
mypy>=1.0.0
```

**Step 2: Install new dependencies**

Run: `uv pip install -r requirements.txt`

Expected: ruff and mypy installed successfully

**Step 3: Verify tools are available**

Run: `uv run ruff --version && uv run mypy --version`

Expected: Both commands output version numbers

**Step 4: Commit**

```bash
git add requirements.txt
git commit -m "build: add ruff and mypy for code quality checks

🤖 Generated with [Claude Code](https://claude.com/claude-code)

Co-Authored-By: Claude <noreply@anthropic.com>"
```

---

## Task 2: Configure Ruff for Linting and Formatting

**Files:**
- Create: `ruff.toml`

**Step 1: Create ruff configuration**

Create `ruff.toml` with the following content:

```toml
# Ruff configuration for discord-download
# https://docs.astral.sh/ruff/

line-length = 100

[lint]
# Enable rule sets:
# E/W - pycodestyle errors and warnings
# F - Pyflakes
# I - isort (import sorting)
# N - pep8-naming
# D - pydocstyle (docstrings)
# UP - pyupgrade (modern Python syntax)
# B - flake8-bugbear (likely bugs)
# S - flake8-bandit (security)
select = ["E", "W", "F", "I", "N", "D", "UP", "B", "S"]

# Ignore specific rules
ignore = [
    "D100",  # Missing docstring in public module (too strict for scripts)
    "D104",  # Missing docstring in public package (too strict)
    "S603",  # subprocess without shell=True (we use subprocess intentionally)
    "S607",  # Starting a process with a partial executable path (intentional)
]

# Exclude generated and temporary directories
exclude = [
    ".git",
    ".venv",
    "__pycache__",
    "exports",
    "public",
    "bin",
    ".worktrees",
]

[lint.per-file-ignores]
# Tests don't need docstrings and can use assert
"tests/**/*.py" = ["D", "S101"]

[lint.pydocstyle]
# Use Google-style docstrings
convention = "google"

[format]
# Use double quotes for strings
quote-style = "double"

# Indent with 4 spaces
indent-style = "space"
```

**Step 2: Run ruff check on codebase**

Run: `uv run ruff check .`

Expected: May show violations that need fixing (we'll address later)

**Step 3: Run ruff format check on codebase**

Run: `uv run ruff format --check .`

Expected: May show formatting issues (we'll address later)

**Step 4: Commit**

```bash
git add ruff.toml
git commit -m "build: add ruff configuration for linting and formatting

Configured with:
- Line length 100
- Google-style docstrings
- Security and bug checks
- Import sorting

🤖 Generated with [Claude Code](https://claude.com/claude-code)

Co-Authored-By: Claude <noreply@anthropic.com>"
```

---

## Task 3: Configure Mypy for Type Checking

**Files:**
- Create: `mypy.ini`

**Step 1: Create mypy configuration**

Create `mypy.ini` with the following content:

```ini
[mypy]
# Target Python version (minimum supported)
python_version = 3.11

# Enable warnings
warn_return_any = True
warn_unused_configs = True
warn_redundant_casts = True

# Disable strict checks initially (can tighten later)
disallow_untyped_defs = False
disallow_incomplete_defs = False
check_untyped_defs = True

# Show error codes for easy suppression
show_error_codes = True

# Exclude directories
exclude = (?x)(
    ^exports/
    | ^public/
    | ^bin/
    | ^\.venv/
    | ^\.worktrees/
  )

# Third-party libraries without type stubs
[mypy-toml]
ignore_missing_imports = True

[mypy-jinja2]
ignore_missing_imports = True
```

**Step 2: Run mypy on scripts directory**

Run: `uv run mypy scripts/`

Expected: May show type errors (we'll track as known issues)

**Step 3: Run mypy on tests directory**

Run: `uv run mypy tests/`

Expected: May show type errors in tests

**Step 4: Document baseline if there are errors**

If mypy shows errors, create a note file:

Run: `uv run mypy scripts/ tests/ 2>&1 | tee mypy-baseline.txt`

This captures current state. We can fix incrementally or add type: ignore comments.

**Step 5: Commit**

```bash
git add mypy.ini
git add mypy-baseline.txt  # Only if file was created
git commit -m "build: add mypy configuration for type checking

Starting with lenient settings to establish baseline.
Can tighten strictness incrementally.

🤖 Generated with [Claude Code](https://claude.com/claude-code)

Co-Authored-By: Claude <noreply@anthropic.com>"
```

---

## Task 4: Create GitHub Actions Workflow

**Files:**
- Create: `.github/workflows/pr-quality-checks.yml`

**Step 1: Create workflow file**

Create `.github/workflows/pr-quality-checks.yml` with the following content:

```yaml
name: PR Quality Checks

on:
  pull_request:
    types: [opened, synchronize, reopened]
  push:
    branches:
      - master
  workflow_dispatch:

jobs:
  test-matrix:
    name: Tests (Python ${{ matrix.python-version }})
    runs-on: ubuntu-latest
    strategy:
      matrix:
        python-version: ['3.11', '3.12']
      fail-fast: false

    steps:
      - name: Checkout code
        uses: actions/checkout@v4

      - name: Set up Python ${{ matrix.python-version }}
        uses: actions/setup-python@v5
        with:
          python-version: ${{ matrix.python-version }}

      - name: Install uv
        run: |
          curl -LsSf https://astral.sh/uv/install.sh | sh
          echo "$HOME/.cargo/bin" >> $GITHUB_PATH

      - name: Cache dependencies
        uses: actions/cache@v4
        with:
          path: ~/.cache/uv
          key: ${{ runner.os }}-uv-${{ hashFiles('requirements.txt') }}
          restore-keys: |
            ${{ runner.os }}-uv-

      - name: Install dependencies
        run: |
          uv venv
          uv pip install -r requirements.txt

      - name: Run tests
        run: uv run pytest -v

  ruff-lint:
    name: Ruff Linting & Formatting
    runs-on: ubuntu-latest

    steps:
      - name: Checkout code
        uses: actions/checkout@v4

      - name: Set up Python 3.12
        uses: actions/setup-python@v5
        with:
          python-version: '3.12'

      - name: Install uv
        run: |
          curl -LsSf https://astral.sh/uv/install.sh | sh
          echo "$HOME/.cargo/bin" >> $GITHUB_PATH

      - name: Cache dependencies
        uses: actions/cache@v4
        with:
          path: ~/.cache/uv
          key: ${{ runner.os }}-uv-${{ hashFiles('requirements.txt') }}
          restore-keys: |
            ${{ runner.os }}-uv-

      - name: Install dependencies
        run: |
          uv venv
          uv pip install -r requirements.txt

      - name: Run ruff linting
        run: uv run ruff check .

      - name: Check code formatting
        run: uv run ruff format --check .

  mypy-typecheck:
    name: Mypy Type Checking
    runs-on: ubuntu-latest

    steps:
      - name: Checkout code
        uses: actions/checkout@v4

      - name: Set up Python 3.12
        uses: actions/setup-python@v5
        with:
          python-version: '3.12'

      - name: Install uv
        run: |
          curl -LsSf https://astral.sh/uv/install.sh | sh
          echo "$HOME/.cargo/bin" >> $GITHUB_PATH

      - name: Cache dependencies
        uses: actions/cache@v4
        with:
          path: ~/.cache/uv
          key: ${{ runner.os }}-uv-${{ hashFiles('requirements.txt') }}
          restore-keys: |
            ${{ runner.os }}-uv-

      - name: Install dependencies
        run: |
          uv venv
          uv pip install -r requirements.txt

      - name: Run mypy
        run: uv run mypy scripts/ tests/

  docs-check:
    name: Documentation Check
    runs-on: ubuntu-latest

    steps:
      - name: Checkout code
        uses: actions/checkout@v4

      - name: Set up Python 3.12
        uses: actions/setup-python@v5
        with:
          python-version: '3.12'

      - name: Install uv
        run: |
          curl -LsSf https://astral.sh/uv/install.sh | sh
          echo "$HOME/.cargo/bin" >> $GITHUB_PATH

      - name: Cache dependencies
        uses: actions/cache@v4
        with:
          path: ~/.cache/uv
          key: ${{ runner.os }}-uv-${{ hashFiles('requirements.txt') }}
          restore-keys: |
            ${{ runner.os }}-uv-

      - name: Install dependencies
        run: |
          uv venv
          uv pip install -r requirements.txt

      - name: Check docstrings
        run: uv run ruff check --select D101,D102,D103 scripts/
```

**Step 2: Verify workflow file syntax**

Run: `cat .github/workflows/pr-quality-checks.yml | head -20`

Expected: See proper YAML formatting

**Step 3: Commit**

```bash
git add .github/workflows/pr-quality-checks.yml
git commit -m "ci: add PR quality verification workflow

Implements comprehensive PR checks:
- Test matrix across Python 3.11/3.12
- Ruff linting and formatting verification
- Mypy type checking
- Documentation coverage (public APIs)

All jobs run in parallel for fast feedback.

🤖 Generated with [Claude Code](https://claude.com/claude-code)

Co-Authored-By: Claude <noreply@anthropic.com>"
```

---

## Task 5: Fix Any Immediate Violations (Optional Cleanup)

**Note:** This task is optional but recommended before the first PR. If there are ruff/mypy violations from the baseline checks, we should fix critical ones.

**Step 1: Check for critical ruff violations**

Run: `uv run ruff check . --select F,E9`

This checks for syntax errors and undefined names (critical failures).

Expected: Ideally no output (no critical errors)

**Step 2: Auto-fix safe violations**

Run: `uv run ruff check . --fix`

Expected: Ruff fixes auto-fixable issues like unused imports, sorting

**Step 3: Format code**

Run: `uv run ruff format .`

Expected: Code formatted to consistent style

**Step 4: Run tests to ensure nothing broke**

Run: `uv run pytest -v`

Expected: All 111 tests still passing

**Step 5: Commit fixes if changes were made**

```bash
git add -A
git commit -m "style: fix ruff linting and formatting issues

Applied automatic fixes from ruff.

🤖 Generated with [Claude Code](https://claude.com/claude-code)

Co-Authored-By: Claude <noreply@anthropic.com>"
```

---

## Task 6: Local Verification

**Files:**
- None (verification only)

**Step 1: Run complete local verification suite**

This simulates what GitHub Actions will run:

```bash
# Test both Python versions (if available, otherwise just current)
uv run pytest -v

# Ruff checks
uv run ruff check .
uv run ruff format --check .

# Mypy checks
uv run mypy scripts/ tests/
```

**Step 2: Document any known issues**

If there are remaining violations that can't be fixed immediately:

Create or update `docs/known-issues.md`:

```markdown
# Known Issues

## Type Checking (mypy)

- `scripts/foo.py:123`: Missing type annotation (non-critical)
- Plan: Add type hints incrementally

## Documentation

- Several internal functions lack docstrings
- Plan: Document public API first, internals later
```

**Step 3: Commit known issues doc if created**

```bash
git add docs/known-issues.md
git commit -m "docs: document known quality check issues

Baseline of existing violations to fix incrementally.

🤖 Generated with [Claude Code](https://claude.com/claude-code)

Co-Authored-By: Claude <noreply@anthropic.com>"
```

---

## Task 7: Final Integration Test

**Files:**
- None (verification only)

**Step 1: Verify all commits were made**

Run: `git log --oneline -7`

Expected: See all commits from this plan

**Step 2: Verify worktree is clean**

Run: `git status`

Expected: "nothing to commit, working tree clean"

**Step 3: Check workflow file is valid**

GitHub doesn't provide local validation, but we can check syntax:

Run: `python3 -c "import yaml; yaml.safe_load(open('.github/workflows/pr-quality-checks.yml'))"`

Expected: No syntax errors (if pyyaml installed), or manually review file

**Step 4: Review README for documentation needs**

Check if README.md mentions testing/quality:

Run: `grep -i "test\|quality\|lint" README.md || echo "No quality docs in README"`

If no documentation exists, consider adding a "Development" section to README.

**Step 5: Prepare for PR**

The workflow is complete and ready to test via PR. Next steps:
1. Push branch to remote
2. Create PR to see workflow run
3. Verify all 4 jobs execute and report status

---

## Verification Commands Summary

After completing all tasks, verify with:

```bash
# Ensure all files exist
ls -la ruff.toml mypy.ini .github/workflows/pr-quality-checks.yml

# Run quality checks locally
uv run pytest -v                    # Should pass (111 tests)
uv run ruff check .                 # Should pass or show known issues
uv run ruff format --check .        # Should pass or show known issues
uv run mypy scripts/ tests/         # Should pass or show known issues

# Check git state
git status                          # Should be clean
git log --oneline -10               # Should show all commits
```

---

## Post-Implementation

After merging this PR, consider:

1. **Incremental strictness**: Gradually enable stricter mypy checks
2. **Coverage reports**: Add pytest-cov and coverage thresholds
3. **Pre-commit hooks**: Add local pre-commit config mirroring CI checks
4. **Security scanning**: Add bandit or safety checks
5. **Documentation**: Update README with development workflow

---

## Troubleshooting

**uv not found in GitHub Actions:**
- Verify uv installation step runs before usage
- Check PATH is updated after installation

**Tests fail in CI but pass locally:**
- Check Python version matrix (test both 3.11 and 3.12 locally)
- Verify dependencies are same (check requirements.txt committed)

**Ruff/mypy too strict:**
- Use per-file ignores in ruff.toml
- Add `type: ignore` comments in code for mypy
- Document exceptions in known-issues.md

**Workflow doesn't trigger:**
- Verify .github/workflows path is correct
- Check YAML syntax is valid
- Ensure triggers (on:) include desired events
