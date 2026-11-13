# Configuration

Every variable read by the code (`src/loadgen/config.py`, the only module that reads the environment; checked 2026-11-13 with `grep -rn 'environ\|getenv' src/`). Bad values stop the run before any request with exit code 2.

| Variable | Default | Required | Meaning |
|---|---|---|---|
| `HOST` | `http://frontend:8080` | no | Base URL of the frontend (scheme, host, port, no path). The only host contacted |
| `USERS` | `5` | no | Simulated users (at least 1) |
| `SPAWN_RATE` | `1` | no | Users started per second (at least 0.01) |
| `RUN_TIME` | `60s` | no | Run length (`30s`, `5m`, `1h30m`); the process exits afterwards |
| `MAX_ORDERS` | `30` | no | Hard cap of successful checkouts per run (all journeys together). `0` = place no orders |
| `MAX_REVIEWS` | `10` | no | Hard cap of posted reviews per run. `0` = post none |
| `FAIL_RATIO` | `0.01` | no | Exit code 1 when failed / total requests is above this (0 to 1) |
| `THINK_MIN` | `1` | no | Seconds a user waits between journeys (lower bound, at least 0) |
| `THINK_MAX` | `3` | no | Upper bound of the wait; must not be below `THINK_MIN` |
| `SOLD_OUT_PRODUCTS` | `volleyball-153` | no | Comma separated product ids with stock 0, used by `out_of_stock` |
| `JOURNEYS` | all | no | Comma separated subset of the journey names (implemented with Locust tags); unknown names are an error |

Set by the Dockerfile, not by the code: `PYTHONPATH=/app/src`, `PYTHONUNBUFFERED=1`, `PYTHONDONTWRITEBYTECODE=1`. Locust itself reads `LOCUST_*` environment variables as defaults for its own options; the program passes all its options on the command line (`__main__.py`), so they are not relevant here (library behaviour, not tested).

The telemetry variables of the other services (`OTEL_*`, `PYROSCOPE_ADDR`, `LOG_LEVEL`) do not exist here: this tool has no telemetry code.
