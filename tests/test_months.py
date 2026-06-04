"""Tests for the months module: month range computation and snowflake conversion."""

from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

import pytest

from scripts.months import (
    current_month_utc,
    month_bounds,
    month_range_iter,
    snowflake_to_datetime,
    snowflake_to_month,
)

# Test constants
WAFER_SPACE_YEAR = 2025
WAFER_SPACE_MONTH = 4
JAN_2020_YEAR = 2020
JAN_2020_MONTH = 1
JAN_2020_DAY = 1
THREE_MONTHS = 3


def test_month_bounds_february_2026() -> None:
    """Month bounds for 2026-02 should bracket all of February (exclusive after, exclusive before).

    --after must be just before start of month so DCE's exclusive boundary still
    includes messages at exactly 00:00:00 on day 1 of the month.
    """
    after, before = month_bounds("2026-02")
    assert after == "2026-01-31T23:59:59.999999+00:00"
    assert before == "2026-03-01T00:00:00+00:00"


def test_month_bounds_january_uses_prior_year() -> None:
    """Month bounds for 2026-01 should reference December 2025 as the lower bound."""
    after, before = month_bounds("2026-01")
    assert after == "2025-12-31T23:59:59.999999+00:00"
    assert before == "2026-02-01T00:00:00+00:00"


def test_month_bounds_december_rolls_to_next_year() -> None:
    """Month bounds for 2025-12 should roll over to January 2026."""
    after, before = month_bounds("2025-12")
    assert after == "2025-11-30T23:59:59.999999+00:00"
    assert before == "2026-01-01T00:00:00+00:00"


def test_month_bounds_rejects_invalid_format() -> None:
    """Invalid month strings raise ValueError."""
    with pytest.raises(ValueError, match="Invalid month"):
        month_bounds("2026-13")
    with pytest.raises(ValueError, match="Invalid month"):
        month_bounds("not-a-month")
    with pytest.raises(ValueError, match="Invalid month"):
        month_bounds("26-01")


def test_month_range_iter_three_months() -> None:
    """Iterating from 2026-01 to 2026-03 should yield three months in order."""
    months = list(month_range_iter("2026-01", "2026-03"))
    assert months == ["2026-01", "2026-02", "2026-03"]
    assert len(months) == THREE_MONTHS


def test_month_range_iter_same_month() -> None:
    """When start equals end, yield only that month."""
    months = list(month_range_iter("2026-05", "2026-05"))
    assert months == ["2026-05"]


def test_month_range_iter_year_rollover() -> None:
    """Iterating across year boundary yields correct sequence."""
    months = list(month_range_iter("2025-11", "2026-02"))
    assert months == ["2025-11", "2025-12", "2026-01", "2026-02"]


def test_month_range_iter_rejects_end_before_start() -> None:
    """Iterator returns empty when end is before start (not an error, just empty)."""
    months = list(month_range_iter("2026-05", "2026-01"))
    assert months == []


def test_snowflake_to_datetime_wafer_space_guild() -> None:
    """The wafer.space guild snowflake should map to roughly April 2025.

    Discord snowflakes encode creation time in the upper 42 bits, with epoch
    starting at Discord's epoch (2015-01-01 UTC).
    """
    dt = snowflake_to_datetime("1361349522684510449")
    assert dt.tzinfo is not None
    assert dt.year == WAFER_SPACE_YEAR
    assert dt.month == WAFER_SPACE_MONTH


def test_snowflake_to_datetime_known_value() -> None:
    """A snowflake with known timestamp converts correctly.

    Discord epoch is 1420070400000 ms (2015-01-01 UTC).
    Snowflake = (timestamp_ms - epoch) << 22.
    For timestamp 2020-01-01 UTC = 1577836800000 ms,
    snowflake = (1577836800000 - 1420070400000) << 22 = 661670957547356160
    """
    # 2020-01-01 00:00:00 UTC
    sf = str((1577836800000 - 1420070400000) << 22)
    dt = snowflake_to_datetime(sf)
    assert dt.year == JAN_2020_YEAR
    assert dt.month == JAN_2020_MONTH
    assert dt.day == JAN_2020_DAY


def test_snowflake_to_datetime_rejects_non_numeric() -> None:
    """Non-numeric snowflake raises ValueError."""
    with pytest.raises(ValueError, match="numeric"):
        snowflake_to_datetime("not-a-number")


def test_snowflake_to_month_returns_yyyymm() -> None:
    """snowflake_to_month returns the YYYY-MM string for the snowflake's creation."""
    month = snowflake_to_month("1361349522684510449")
    assert month == "2025-04"


def test_current_month_utc_format() -> None:
    """current_month_utc returns YYYY-MM format from UTC now."""
    with patch("scripts.months.datetime") as mock_dt:
        mock_dt.now.return_value = datetime(2026, 5, 11, 12, 0, 0, tzinfo=timezone.utc)
        mock_dt.side_effect = lambda *a, **kw: datetime(*a, **kw)
        result = current_month_utc()
        assert result == "2026-05"


def test_is_month_dir_name() -> None:
    """is_month_dir_name accepts YYYY-MM strings and rejects others."""
    from scripts.months import is_month_dir_name

    assert is_month_dir_name("2026-05") is True
    assert is_month_dir_name("2025-12") is True
    assert is_month_dir_name("2026-01") is True
    assert is_month_dir_name("2026-13") is False  # Invalid month
    assert is_month_dir_name("2026-00") is False  # Invalid month
    assert is_month_dir_name("26-05") is False  # Wrong format
    assert is_month_dir_name("2026-5") is False  # Wrong format
    assert is_month_dir_name("not-a-date") is False
    assert is_month_dir_name("index") is False
    assert is_month_dir_name("") is False


def test_scan_completed_months_finds_month_directories(tmp_path: Path) -> None:
    """scan_completed_months returns months that have a non-empty HTML file."""
    from scripts.months import scan_completed_months

    channel_dir = tmp_path / "general"
    (channel_dir / "2026-01").mkdir(parents=True)
    (channel_dir / "2026-01" / "2026-01.html").write_text("<html>jan</html>")
    (channel_dir / "2026-02").mkdir()
    (channel_dir / "2026-02" / "2026-02.html").write_text("<html>feb</html>")
    # Empty HTML file should not count
    (channel_dir / "2026-03").mkdir()
    (channel_dir / "2026-03" / "2026-03.html").write_text("")
    # Missing HTML file should not count
    (channel_dir / "2026-04").mkdir()
    # Non-month directory should be ignored
    (channel_dir / "media").mkdir()

    completed = scan_completed_months(channel_dir)
    assert completed == {"2026-01", "2026-02"}


def test_scan_completed_months_empty_when_dir_missing(tmp_path: Path) -> None:
    """A missing channel directory has no completed months."""
    from scripts.months import scan_completed_months

    completed = scan_completed_months(tmp_path / "does-not-exist")
    assert completed == set()


def test_scan_completed_months_skips_cross_month_jsons(tmp_path: Path) -> None:
    """A month whose JSON has messages from a different month is NOT complete.

    This is the legacy-data case: the old code dumped all messages into
    the export-time current month, so `2025-11/2025-11.json` actually
    holds messages timestamped 2025-04 through 2025-11. We must re-export
    those months properly, not skip them.
    """
    import json as _json

    from scripts.months import scan_completed_months

    channel_dir = tmp_path / "general"
    month_dir = channel_dir / "2025-11"
    month_dir.mkdir(parents=True)
    (month_dir / "2025-11.html").write_text("<html>mixed</html>")
    (month_dir / "2025-11.json").write_text(
        _json.dumps(
            {
                "messages": [
                    {"id": "1", "timestamp": "2025-04-10T00:00:00+00:00"},
                    {"id": "2", "timestamp": "2025-11-20T00:00:00+00:00"},
                ]
            }
        )
    )

    # A correctly-partitioned month next to it. The HTML must render the same
    # one message the JSON holds (data-message-id) so the consistency gate
    # counts it as complete.
    pure_month = channel_dir / "2026-05"
    pure_month.mkdir()
    (pure_month / "2026-05.html").write_text("<html><div data-message-id=10>hi</div></html>")
    (pure_month / "2026-05.json").write_text(
        _json.dumps({"messages": [{"id": "10", "timestamp": "2026-05-02T00:00:00+00:00"}]})
    )

    completed = scan_completed_months(channel_dir)
    # 2025-11 must be re-exported; 2026-05 is honest and skipped.
    assert completed == {"2026-05"}


def test_scan_completed_months_excludes_divergent_month(tmp_path: Path) -> None:
    """A month whose JSON holds more messages than the HTML renders (issue #1
    divergence) is NOT complete, so it re-exports and heals."""
    import json as _json

    from scripts.months import scan_completed_months

    chan = tmp_path / "general"
    month = chan / "2026-04"
    month.mkdir(parents=True)
    # JSON says 3 messages; HTML renders only 1 → divergent.
    (month / "2026-04.json").write_text(
        _json.dumps(
            {
                "messages": [
                    {"id": "1", "timestamp": "2026-04-01T00:00:00+00:00"},
                    {"id": "2", "timestamp": "2026-04-02T00:00:00+00:00"},
                    {"id": "3", "timestamp": "2026-04-03T00:00:00+00:00"},
                ]
            }
        )
    )
    (month / "2026-04.html").write_text("<html><div data-message-id=1>only one</div></html>")

    assert scan_completed_months(chan) == set()


def test_count_html_messages_counts_data_message_id(tmp_path: Path) -> None:
    """count_html_messages counts DCE's unquoted data-message-id= markers and
    ignores the chatlog__message-container- tokens in CSS/JS."""
    from scripts.months import count_html_messages

    ids = ["111", "222"]
    html = tmp_path / "m.html"
    html.write_text(
        "".join(f"<div data-message-id={i}>x</div>" for i in ids)
        + "<style>.chatlog__message-container--pinned{}</style>"
    )
    assert count_html_messages(html) == len(ids)


def test_count_divergent_months(tmp_path: Path) -> None:
    """count_divergent_months counts months where JSON and HTML counts differ."""
    import json as _json

    from scripts.months import count_divergent_months

    chan = tmp_path / "general"
    ok = chan / "2026-05"
    ok.mkdir(parents=True)
    (ok / "2026-05.json").write_text(_json.dumps({"messages": [{"id": "1"}]}))
    (ok / "2026-05.html").write_text("<div data-message-id=1>x</div>")
    bad = chan / "2026-04"
    bad.mkdir()
    (bad / "2026-04.json").write_text(_json.dumps({"messages": [{"id": "1"}, {"id": "2"}]}))
    (bad / "2026-04.html").write_text("<html>blank</html>")

    assert count_divergent_months(chan) == 1


def test_scan_completed_months_treats_empty_json_as_complete(tmp_path: Path) -> None:
    """An empty messages array is consistent with any month tag — count as done."""
    import json as _json

    from scripts.months import scan_completed_months

    channel_dir = tmp_path / "general"
    month_dir = channel_dir / "2026-03"
    month_dir.mkdir(parents=True)
    (month_dir / "2026-03.html").write_text("<html>empty</html>")
    (month_dir / "2026-03.json").write_text(_json.dumps({"messages": []}))

    completed = scan_completed_months(channel_dir)
    assert completed == {"2026-03"}


def test_count_nonempty_months_uses_json_size(tmp_path: Path) -> None:
    """count_nonempty_months counts months whose JSON is bigger than an empty
    DCE export (a cheap os.stat heuristic — empty 0-message JSON is ~500B,
    one with messages is multi-KB). Used to prioritize starved entries.
    """
    from scripts.months import count_nonempty_months

    chan = tmp_path / "thread-a"
    # Empty current-month export: tiny JSON (DCE 0-message scaffold ~500B).
    (chan / "2026-05").mkdir(parents=True)
    (chan / "2026-05" / "2026-05.html").write_text("<html>0</html>")
    (chan / "2026-05" / "2026-05.json").write_text('{"messages":[]}')  # ~15B
    # A month with real messages: large JSON.
    (chan / "2026-03").mkdir(parents=True)
    (chan / "2026-03" / "2026-03.html").write_text("<html>real</html>")
    (chan / "2026-03" / "2026-03.json").write_text("x" * 5000)

    assert count_nonempty_months(chan) == 1  # only 2026-03 has real data


def test_count_nonempty_months_zero_for_only_empty(tmp_path: Path) -> None:
    """A thread that only has an empty current-month export counts as 0 —
    this is exactly the 'empty thread' case that must be prioritized."""
    from scripts.months import count_nonempty_months

    chan = tmp_path / "starved-thread"
    (chan / "2026-05").mkdir(parents=True)
    (chan / "2026-05" / "2026-05.json").write_text('{"messages":[]}')

    assert count_nonempty_months(chan) == 0


def test_count_nonempty_months_missing_dir_is_zero(tmp_path: Path) -> None:
    """No public dir yet → zero non-empty months (maximally starved)."""
    from scripts.months import count_nonempty_months

    assert count_nonempty_months(tmp_path / "nope") == 0
