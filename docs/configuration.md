# Configuration

Every variable read by the code (`src/loadgen/config.py`, plus `LOADGEN_PASSWORD` in `journeys.py`; the only places that read the environment, checked 2026-11-14 with `grep -rn 'environ\|getenv' src/`). Bad values stop the run before any request with exit code 2.

| Variable | Default | Required | Meaning |
|---|---|---|---|
| `HOST` | `http://frontend:8080` | no | Base URL of the frontend (scheme, host, port, no path). The only host contacted |
| `USERS` | `5` | no | Simulated users (at least 1) |
| `SPAWN_RATE` | `1` | no | Users started per second (at least 0.01) |
| `RUN_TIME` | `60s` | no | Run length (`30s`, `5m`, `1h30m`); the process exits afterwards |
| `MAX_ORDERS` | `30` | no | Hard cap of successful checkouts per run (all journeys together). `0` = place no orders |
| `MAX_REVIEWS` | `10` | no | Hard cap of posted reviews per run. `0` = post none |
| `REQUEST_TIMEOUT` | `30` | no | Seconds one HTTP request may take (connect and read, 0.1 to 300). A request that takes longer counts as a failed request with status 0 |
| `FAIL_RATIO` | `0.01` | no | Exit code 1 when failed / total requests is above this (0 to 1) |
| `THINK_MIN` | `1` | no | Seconds a user waits between journeys (lower bound, at least 0) |
| `THINK_MAX` | `3` | no | Upper bound of the wait; must not be below `THINK_MIN` |
| `SOLD_OUT_PRODUCTS` | `volleyball-153` | no | Comma separated product ids with stock 0, used by `out_of_stock` |
| `LOADGEN_PASSWORD` | random per process | no | Password of the demo accounts the `account` journey registers (the shop accepts 8 to 72 bytes). Unset or empty: a random 22 character token (`secrets.token_urlsafe(16)`), different in every process. Read in `journeys.py`, not in `config.py` |
| `JOURNEYS` | all | no | Comma separated subset of the journey names (implemented with Locust tags); unknown names are an error |

Set by the Dockerfile, not by the code: `PYTHONPATH=/app/src`, `PYTHONUNBUFFERED=1`, `PYTHONDONTWRITEBYTECODE=1`. Locust itself reads `LOCUST_*` environment variables as defaults for its own options; the program passes all its options on the command line (`__main__.py`), so they are not relevant here (library behaviour, not tested).

The telemetry variables of the other services (`OTEL_*`, `PYROSCOPE_ADDR`, `LOG_LEVEL`) do not exist here: this tool has no telemetry code.
