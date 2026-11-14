"""Run configuration, read once from the environment (see the README table)."""

from __future__ import annotations

import os
import re
from collections.abc import Mapping
from dataclasses import dataclass

DEFAULT_HOST = "http://frontend:8080"
# Locust accepts "30s", "5m", "1h30m"; anything else would fail late with an unclear message.
_DURATION = re.compile(r"^(\d+[hms])+$")


# journey names = task names in journeys.py = values of JOURNEYS
JOURNEY_NAMES = (
    "browse",
    "product_view",
    "add_to_cart",
    "checkout_success",
    "checkout_declined",
    "out_of_stock",
    "review",
    "account",
)


class ConfigError(ValueError):
    """An environment variable has a value that cannot be used."""


def _int(env: Mapping[str, str], name: str, default: int, minimum: int) -> int:
    raw = env.get(name, "").strip()
    if not raw:
        return default
    try:
        value = int(raw)
    except ValueError:
        raise ConfigError(f"{name}={raw!r} is not an integer") from None
    if value < minimum:
        raise ConfigError(f"{name}={value} must be at least {minimum}")
    return value


def _float(env: Mapping[str, str], name: str, default: float, minimum: float, maximum: float | None = None) -> float:
    raw = env.get(name, "").strip()
    if not raw:
        return default
    try:
        value = float(raw)
    except ValueError:
        raise ConfigError(f"{name}={raw!r} is not a number") from None
    if value < minimum or (maximum is not None and value > maximum):
        upper = f" and at most {maximum}" if maximum is not None else ""
        raise ConfigError(f"{name}={value} must be at least {minimum}{upper}")
    return value


@dataclass(frozen=True)
class Config:
    host: str = DEFAULT_HOST
    users: int = 5
    spawn_rate: float = 1.0
    run_time: str = "60s"
    max_orders: int = 30
    max_reviews: int = 10
    fail_ratio: float = 0.01
    request_timeout: float = 30.0  # seconds per HTTP request (CODE-05)
    think_min: float = 1.0
    think_max: float = 3.0
    sold_out_products: tuple[str, ...] = ("volleyball-153",)
    journeys: tuple[str, ...] = ()  # empty = all of JOURNEY_NAMES

    @classmethod
    def from_env(cls, env: Mapping[str, str] | None = None) -> Config:
        env = os.environ if env is None else env
        host = env.get("HOST", "").strip().rstrip("/") or DEFAULT_HOST
        if not re.match(r"^https?://[^/\s]+$", host):
            raise ConfigError(f"HOST={host!r} must look like http://name:port (no path)")
        run_time = env.get("RUN_TIME", "").strip() or cls.run_time
        if not _DURATION.match(run_time):
            raise ConfigError(f"RUN_TIME={run_time!r} must look like 30s, 5m or 1h30m")
        think_min = _float(env, "THINK_MIN", cls.think_min, 0.0)
        think_max = _float(env, "THINK_MAX", cls.think_max, 0.0)
        if think_max < think_min:
            raise ConfigError(f"THINK_MAX={think_max} must not be below THINK_MIN={think_min}")
        sold_out = tuple(p.strip() for p in env.get("SOLD_OUT_PRODUCTS", "").split(",") if p.strip())
        journeys = tuple(j.strip() for j in env.get("JOURNEYS", "").split(",") if j.strip())
        unknown = [j for j in journeys if j not in JOURNEY_NAMES]
        if unknown:
            raise ConfigError(f"JOURNEYS has unknown names {unknown}; known: {', '.join(JOURNEY_NAMES)}")
        return cls(
            host=host,
            users=_int(env, "USERS", cls.users, 1),
            spawn_rate=_float(env, "SPAWN_RATE", cls.spawn_rate, 0.01),
            run_time=run_time,
            max_orders=_int(env, "MAX_ORDERS", cls.max_orders, 0),
            max_reviews=_int(env, "MAX_REVIEWS", cls.max_reviews, 0),
            fail_ratio=_float(env, "FAIL_RATIO", cls.fail_ratio, 0.0, 1.0),
            request_timeout=_float(env, "REQUEST_TIMEOUT", cls.request_timeout, 0.1, 300.0),
            think_min=think_min,
            think_max=think_max,
            sold_out_products=sold_out or cls.sold_out_products,
            journeys=journeys,
        )
