# PR Quality Verification Workflow Design

**Date:** 2025-11-16
**Status:** Approved

## Overview

This design establishes automated quality verification for pull requests using GitHub Actions. The workflow ensures code quality, type safety, test coverage, and documentation standards before code is merged.

## Requirements

### Quality Checks
- **Testing:** Run full pytest suite to verify functionality
- **Linting:** Check code style and catch common errors
- **Type Checking:** Validate type hints with mypy
- **Formatting:** Ensure consistent code formatting
- **Documentation:** Verify docstring coverage for public APIs

### Tooling Decisions
- **Ruff:** All-in-one tool for linting, formatting, and import sorting
- **Mypy:** Type checking for static analysis
- **Pytest:** Existing test framework
- **UV:** Package management (project standard)

### Enforcement
- All checks must report failures clearly (red status on issues)
- Checks run on PR events and master branch pushes
- No silent failures - explicit error reporting required

## Architecture

### Workflow Structure

**File:** `.github/workflows/pr-quality-checks.yml`

**Triggers:**
- Pull request events: opened, synchronized, reopened
- Push to master branch (verify master stays healthy)
- Manual workflow dispatch (for testing)

**Jobs:** 4 parallel jobs for fast feedback
1. test-matrix (pytest across Python versions)
2. ruff-lint (code style and formatting)
3. mypy-typecheck (type validation)
4. docs-check (documentation coverage)

### Design Rationale

**Matrix tests + static analysis approach chosen because:**
- Tests multiple Python versions (3.11, 3.12) in parallel
- Future-proof for version compatibility
- Fast feedback through parallel job execution
- Clear failure isolation (easy to see which check failed)
- Best of both worlds: comprehensive coverage + speed

**Alternative approaches considered:**
- Separate parallel jobs: Good but no Python version matrix
- Single comprehensive job: Simpler but slower and less granular

## Component Details

### Job 1: Test Matrix

**Purpose:** Verify functionality across Python versions

**Configuration:**
```yaml
strategy:
  matrix:
    python-version: ['3.11', '3.12']
runs-on: ubuntu-latest
```

**Steps:**
1. Checkout code
2. Install uv
3. Set up Python (matrix version)
4. Install dependencies: `uv pip install -r requirements.txt`
5. Run tests: `uv run pytest -v`

**Success Criteria:** All tests pass on both Python versions

**Caching:** UV dependencies cached by hash of requirements.txt

### Job 2: Ruff Linting and Formatting

**Purpose:** Enforce code style and formatting standards

**Configuration:**
- Python 3.12 on ubuntu-latest
- Single job (linting doesn't need version matrix)

**Steps:**
1. Checkout code
2. Install uv
3. Set up Python 3.12
4. Install dependencies
5. Run linting: `uv run ruff check .`
6. Verify formatting: `uv run ruff format --check .`

**Success Criteria:**
- No linting errors from ruff check
- No formatting violations from ruff format --check
- Both commands use --check mode (no file modifications)

**Configuration Required:** `ruff.toml` or `pyproject.toml` with:
- Line length (recommend 100)
- Select rule sets (recommend: E, F, W, I, N, D)
- Exclude patterns (exports/, public/, bin/)

### Job 3: Mypy Type Checking

**Purpose:** Validate type hints and catch type-related bugs

**Configuration:**
- Python 3.12 on ubuntu-latest
- Checks both scripts/ and tests/ directories

**Steps:**
1. Checkout code
2. Install uv
3. Set up Python 3.12
4. Install dependencies
5. Run type check: `uv run mypy scripts/ tests/`

**Success Criteria:** No type errors reported

**Configuration Required:** `mypy.ini` or `pyproject.toml` with:
- Python version: 3.11 (minimum supported)
- Strictness level (recommend starting lenient, increase over time)
- Exclude patterns
- Plugin support if needed (e.g., pytest plugin)

**Initial Baseline:** May need to add type: ignore comments for existing code

### Job 4: Documentation Check

**Purpose:** Ensure public APIs are documented

**Configuration:**
- Python 3.12 on ubuntu-latest
- Focuses on scripts/ directory (main codebase)

**Steps:**
1. Checkout code
2. Install uv
3. Set up Python 3.12
4. Install dependencies
5. Check docstrings: `uv run ruff check --select D .` or `uv run pydocstyle scripts/`

**Success Criteria:** All public functions, classes, and modules have docstrings

**Approach:** Use ruff's D-series rules (pydocstyle compatibility) for simplicity
- D100: Missing docstring in public module
- D101: Missing docstring in public class
- D102: Missing docstring in public method
- D103: Missing docstring in public function

**Configuration Required:** Configure which docstring conventions to follow (Google, NumPy, or PEP 257)

## Configuration Files Needed

### 1. Workflow File
- `.github/workflows/pr-quality-checks.yml`
- Defines all jobs and their configurations

### 2. Ruff Configuration
- `ruff.toml` or `[tool.ruff]` in `pyproject.toml`
- Line length, rule selections, excludes, per-file ignores

### 3. Mypy Configuration
- `mypy.ini` or `[tool.mypy]` in `pyproject.toml`
- Python version, strictness, plugins, excludes

### 4. Dependency Updates
- Add to requirements.txt (if not present):
  - ruff
  - mypy
  - pytest (already present)

## Implementation Considerations

### Incremental Adoption
- Start with lenient type checking, tighten over time
- May need type: ignore comments for existing code initially
- Documentation checks can start with just public modules/classes

### Performance Optimization
- Cache uv dependencies across jobs (shared cache key)
- Matrix jobs run in parallel for fast feedback
- Static analysis jobs independent and parallel

### Failure Reporting
- Each job explicitly fails on errors (default GitHub Actions behavior)
- Clear step labels for easy debugging
- Verbose output for test failures

### Integration with Existing Workflows
- Completely independent from export-and-publish.yml
- Runs only on PRs and master pushes (not scheduled)
- No deployment or publishing steps

## Success Metrics

- All quality checks pass before merge
- PRs show clear red/green status for each check
- Developers can identify specific failures easily
- Workflow completes in < 5 minutes (parallel execution)

## Future Enhancements

- Coverage reporting with codecov/coveralls
- Security scanning with bandit
- Dependency vulnerability scanning with safety
- Pre-commit hooks for local verification
- Expand Python version matrix as needed
