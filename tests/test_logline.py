"""The JSON lines this program writes itself: the bad-configuration error (CODE-01) and the start line (CODE-06)."""

import json
from datetime import UTC, datetime, timedelta, timezone

import pytest

from loadgen import __main__ as entry
from loadgen import logline

FIXED = datetime(2026, 11, 14, 22, 13, 20, 123456, tzinfo=UTC)


def test_golden_line_with_an_injected_clock():
    text = logline.line("info", "starting", env={"SERVICE_VERSION": "1.2.3"}, now=lambda: FIXED, commit="abc")
    assert json.loads(text) == {
        "timestamp": "2026-11-14T22:13:20.123Z",
        "severity": "info",
        "message": "starting",
        "service": "load-generator",
        "version": "1.2.3",
        "commit": "abc",
    }
    assert "\n" not in text


def test_the_timestamp_is_utc_whatever_zone_the_clock_returns():
    plus_two = FIXED.astimezone(timezone(timedelta(hours=2)))
    assert (
        json.loads(logline.line("info", "x", env={}, now=lambda: plus_two))["timestamp"] == "2026-11-14T22:13:20.123Z"
    )


def test_version_and_commit_default_when_the_image_build_did_not_set_them():
    assert (logline.version({}), logline.commit({})) == ("dev", "unknown")
    assert (logline.version({"SERVICE_VERSION": " "}), logline.commit({"SERVICE_COMMIT": ""})) == ("dev", "unknown")
    assert logline.commit({"SERVICE_COMMIT": "deadbeef"}) == "deadbeef"


def test_quotes_and_newlines_stay_valid_json():
    record = json.loads(logline.line("error", 'HOST="a"\nb', env={}))
    assert record["message"] == 'HOST="a"\nb'


def test_a_bad_configuration_is_one_json_line_on_stderr_and_exit_2(monkeypatch, capsys):
    monkeypatch.setenv("HOST", "frontend:8080")
    with pytest.raises(SystemExit) as exit_info:
        entry.main()
    assert exit_info.value.code == 2
    out, err = capsys.readouterr()
    assert out == ""
    record = json.loads(err)  # exactly one JSON object, nothing else
    assert record["severity"] == "error" and record["service"] == "load-generator"
    assert "HOST" in record["message"] and record["message"].startswith("bad configuration")


def test_start_line_carries_version_commit_and_the_settings(monkeypatch, capsys):
    monkeypatch.setenv("SERVICE_VERSION", "9.9.9")
    monkeypatch.setenv("SERVICE_COMMIT", "cafe123")
    monkeypatch.setenv("USERS", "2")
    monkeypatch.setenv("REQUEST_TIMEOUT", "7.5")
    monkeypatch.setattr("locust.main.main", lambda: None)  # do not start a run
    entry.main()
    record = json.loads(capsys.readouterr().out.splitlines()[0])
    assert record["message"] == "starting"
    assert (record["version"], record["commit"]) == ("9.9.9", "cafe123")
    assert (record["users"], record["request_timeout_seconds"]) == (2, 7.5)
