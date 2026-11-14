"""One JSON log line in the platform's standard shape (timestamp, severity, message, service, version)."""

from __future__ import annotations

import json
import os
from collections.abc import Callable, Mapping
from datetime import UTC, datetime

SERVICE = "load-generator"


def version(env: Mapping[str, str] | None = None) -> str:
    env = os.environ if env is None else env
    return env.get("SERVICE_VERSION", "").strip() or "dev"


def commit(env: Mapping[str, str] | None = None) -> str:
    env = os.environ if env is None else env
    return env.get("SERVICE_COMMIT", "").strip() or "unknown"


def utc_now() -> datetime:
    return datetime.now(UTC)


def line(
    severity: str,
    message: str,
    *,
    env: Mapping[str, str] | None = None,
    now: Callable[[], datetime] = utc_now,
    **fields: object,
) -> str:
    """The JSON text of one log line. `now` returns an aware UTC time (injected in tests)."""
    stamp = now().astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"
    record = {
        "timestamp": stamp,
        "severity": severity,
        "message": message,
        "service": SERVICE,
        "version": version(env),
        **fields,
    }
    return json.dumps(record, ensure_ascii=False)
