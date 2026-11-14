"""Entry point: `python -m loadgen` runs Locust headless with the settings from the environment."""

from __future__ import annotations

import sys
from pathlib import Path

from . import logline
from .config import Config, ConfigError


def build_argv(cfg: Config, locustfile: str) -> list[str]:
    argv = [
        "locust",
        "-f", locustfile,
        "--headless",
        "--only-summary",
        "--host", cfg.host,
        "--users", str(cfg.users),
        "--spawn-rate", str(cfg.spawn_rate),
        "--run-time", cfg.run_time,
        "--stop-timeout", "30",
    ]  # fmt: skip
    if cfg.journeys:
        argv += ["--tags", *cfg.journeys]
    return argv


def main() -> None:
    try:
        cfg = Config.from_env()
    except ConfigError as exc:
        # CODE-01: a configuration error is one JSON line, not prose
        print(logline.line("error", f"bad configuration: {exc}"), file=sys.stderr, flush=True)
        sys.exit(2)
    # CODE-06: version and commit (set by the image build) are logged once at start
    print(
        logline.line(
            "info",
            "starting",
            commit=logline.commit(),
            host=cfg.host,
            users=cfg.users,
            run_time=cfg.run_time,
            request_timeout_seconds=cfg.request_timeout,
        ),
        flush=True,
    )
    locustfile = str(Path(__file__).with_name("journeys.py"))
    sys.argv = build_argv(cfg, locustfile)
    from locust.main import main as locust_main

    locust_main()


if __name__ == "__main__":
    main()
