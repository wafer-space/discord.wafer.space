# Known Issues

This document tracks known violations from quality checks that exist as of 2025-11-16. These are non-critical issues that can be addressed incrementally.

## Summary

- **Tests**: ALL PASSING (111/111)
- **Ruff Linting**: 17 violations (1 E501, 2 B904, 1 B007, 13 N806, 1 E501 in tests)
- **Ruff Formatting**: PASSING (all files formatted)
- **Mypy Type Checking**: 82 errors across 12 files

## Test Suite

**Status**: PASSING

All 111 tests pass successfully in 0.45 seconds:
- 8 tests in test_channel_classifier.py
- 6 tests in test_config.py
- 8 tests in test_export_channels.py
- 18 tests in test_export_orchestration.py
- 8 tests in test_fetch_channels.py
- 14 tests in test_generate_navigation.py
- 9 tests in test_generate_navigation_main.py
- 13 tests in test_organize_exports.py
- 8 tests in test_state.py
- 11 tests in test_templates.py
- 8 tests in test_thread_metadata.py

## Ruff Linting Issues

**Total**: 17 violations (all non-critical)

### B904: Missing exception chaining (2 violations)

**File**: `scripts/export_channels.py`
**Lines**: 196, 198

```python
# Line 196
except subprocess.TimeoutExpired:
    raise RuntimeError("Channel fetching timed out after 30 seconds")

# Line 198
except Exception as e:
    raise RuntimeError(f"Channel fetching failed: {str(e)}")
```

**Fix**: Use `raise ... from err` or `raise ... from None`:
```python
except subprocess.TimeoutExpired as e:
    raise RuntimeError("Channel fetching timed out after 30 seconds") from e
except Exception as e:
    raise RuntimeError(f"Channel fetching failed: {str(e)}") from e
```

**Impact**: Low - Slightly less informative stack traces, but error messages are clear

---

### E501: Line too long (2 violations)

**File**: `scripts/organize_exports.py`, line 116
**Length**: 114 characters (limit: 100)

```python
f"  ✓ {forum_name}/{thread_name}{extension} → {dest_file.relative_to(public_dir)}"
```

**File**: `tests/test_export_orchestration.py`, line 644
**Length**: 102 characters (limit: 100)

```python
# Check that format_export_command was called with after_timestamp
```

**Fix**: Break into multiple lines or shorten variable names

**Impact**: Low - Style only, no functional impact

---

### B007: Unused loop variable (1 violation)

**File**: `tests/test_config.py`, line 41

```python
for server_key, server_config in config["servers"].items():
    # Should have forum_channels list
    assert "forum_channels" in server_config
```

**Fix**: Rename to `_server_key` to indicate intentionally unused:
```python
for _server_key, server_config in config["servers"].items():
```

**Impact**: Low - Code works correctly, just a style preference

---

### N806: Variable should be lowercase (13 violations in tests)

**File**: `tests/test_export_orchestration.py`

Multiple instances of mock variables using PascalCase instead of snake_case:
- `MockState` (11 occurrences on lines: 139, 179, 219, 259, 298, 345, 386, 418, 441, 486, 545)
- `MockPath` (1 occurrence on line 423)

**Example**:
```python
with patch("scripts.export_channels.StateManager") as MockState:
    mock_state_instance = Mock()
    MockState.return_value = mock_state_instance
```

**Fix**: Use lowercase variable names:
```python
with patch("scripts.export_channels.StateManager") as mock_state_class:
    mock_state_instance = Mock()
    mock_state_class.return_value = mock_state_instance
```

**Impact**: Low - PEP 8 style violation in tests only, no functional impact

## Ruff Formatting

**Status**: PASSING

All 21 files are properly formatted. No formatting issues detected.

## Mypy Type Checking Issues

**Total**: 82 errors across 12 files

### Category Breakdown

1. **Optional/None type issues** (33 errors)
   - Implicit Optional parameters not allowed
   - None values used where non-None expected
   - Missing type narrowing after None checks

2. **Type annotation issues** (28 errors)
   - Return types declared as specific types but returning Any
   - Incompatible types in assignments (Path vs str)
   - Unsupported operations on generic object types

3. **Dict/List type mismatches** (21 errors)
   - Dict value types incompatible (e.g., `str | None` vs `str`)
   - List item types incompatible
   - Indexing possibly None values

### Key Files with Issues

**scripts/export_channels.py** (7 errors)
- Optional str in subprocess commands
- Return type mismatches
- Object type operations (append, +)

**scripts/organize_exports.py** (13 errors)
- Implicit Optional parameters (exports_dir, public_dir)
- Object type arithmetic
- Return type mismatches

**scripts/generate_navigation.py** (12 errors)
- Implicit Optional parameters
- None passed where str expected
- Object type operations

**scripts/channel_classifier.py** (1 error)
- Implicit Optional for thread_id parameter

**scripts/config.py** (1 error)
- Returning Any from typed function

**scripts/state.py** (2 errors)
- Returning Any from typed functions

**scripts/test_bot_access.py** (1 error)
- List item type mismatch (str | None)

**tests/** files (45 errors)
- Type mismatches in test data construction
- Path vs str assignments
- Indexing possibly None values without checks

### Remediation Strategy

The mypy configuration is intentionally lenient (`disallow_untyped_defs = False`) to establish a baseline. Recommended approach:

1. **Phase 1**: Fix critical errors in production code (scripts/)
   - Add explicit `Optional` type hints
   - Fix implicit Optional parameters
   - Add type narrowing for None checks

2. **Phase 2**: Improve type coverage incrementally
   - Add type hints to function signatures
   - Use TypedDict for structured dicts
   - Enable stricter checks gradually

3. **Phase 3**: Clean up test type issues
   - Most test errors are non-critical
   - Can add `# type: ignore` comments for mock-related issues
   - Focus on production code type safety first

### Example Fixes

**Implicit Optional**:
```python
# Before
def organize_exports(exports_dir: Path = None, public_dir: Path = None):

# After
from typing import Optional
def organize_exports(exports_dir: Optional[Path] = None, public_dir: Optional[Path] = None):
```

**Return Type Any**:
```python
# Before
def load_config(config_path: str = "config.toml") -> dict:
    return toml.load(config_path)

# After
from typing import Any
def load_config(config_path: str = "config.toml") -> dict[str, Any]:
    return toml.load(config_path)
```

**None Indexing**:
```python
# Before
metadata = extract_thread_metadata(path)
title = metadata["title"]  # Error if metadata is None

# After
metadata = extract_thread_metadata(path)
if metadata is not None:
    title = metadata["title"]
```

## Conclusion

The codebase is in good shape:
- All tests passing
- Code is properly formatted
- Linting issues are minor style violations
- Type checking errors are mostly about strictness, not bugs

These issues can be addressed incrementally without blocking the PR. The quality checks workflow will help prevent new violations while we clean up existing ones.
