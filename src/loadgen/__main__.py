"""Entry point: `python -m loadgen` runs Locust headless with the settings from the environment."""

from __future__ import annotations

import sys
from pathlib import Path

from .config import Config, ConfigError


def build_argv(cfg: Config, locustfile: str) -> list[str]:
    return [
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


def main() -> None:
    try:
        cfg = Config.from_env()
    except ConfigError as exc:
        print(f"loadgen: bad configuration: {exc}", file=sys.stderr)
        sys.exit(2)
    locustfile = str(Path(__file__).with_name("journeys.py"))
    sys.argv = build_argv(cfg, locustfile)
    from locust.main import main as locust_main

    locust_main()


if __name__ == "__main__":
    main()
