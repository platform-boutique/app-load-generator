# load-generator

## Purpose and place in the shop

A small [Locust](https://locust.io) project that drives the Everly storefront (the `frontend` service) with weighted, realistic visitor journeys and prints a summary. It is a batch tool, not a server: it speaks HTTP to the frontend only (no gRPC, no direct calls to other services), never contacts anything except `HOST`, runs for `RUN_TIME` and exits. It is a test client for the local compose stack: it places real (demo) orders, registers demo accounts and posts a few demo reviews, so it has hard caps (`MAX_ORDERS`, `MAX_REVIEWS`) and is polite by default (5 users, spawn rate 1, 1 to 3 s think time).

Context diagram and the flow of a journey: [`docs/architecture.md`](docs/architecture.md).

| | |
|---|---|
| Language / runtime | Python 3.12 (`.python-version`, ruff `target-version`, image `python:3.12-slim` all say 3.12), Locust 2.47.0 |
| Image | built locally only: `platform-demo/load-generator:local` (`Dockerfile`, user `10001:10001`, no port, no HEALTHCHECK: batch tool) |
| Ports | none (headless run, no web UI) |
| State | none; a run leaves demo data in the shop (see Data) |
| Depends on | the `frontend` over HTTP (`HOST`, default `http://frontend:8080`) |
| Called by | nobody; started by hand or by the compose profile `loadgen` (`local/compose.yaml`) |

## Status

No CI pipeline, GitHub repository, Helm chart or Backstage registration exists yet; the service is built and run locally only. Status badges are added when the repo has a pipeline. The CI notes for the shared Python pipeline are in Develop.

## Quick start

Locally, against the compose stack in `local/` (shop at http://localhost:8080). The commands were run for this change as far as the Develop table says; the 2026-11-01 runs are in `docs/development.md`.

```bash
uv venv --python 3.12 .venv
uv pip install --python .venv/bin/python -r requirements.txt -r requirements-dev.txt
HOST=http://localhost:8080 USERS=5 SPAWN_RATE=1 RUN_TIME=30s MAX_ORDERS=5 PYTHONPATH=src .venv/bin/python -m loadgen
```

As a container (no port, UID 10001; `--network host` to reach a published port on the host, or the compose network with `HOST=http://frontend:8080`):

```bash
docker build -t platform-demo/load-generator:local .
docker run --rm --network host -e HOST=http://localhost:8080 -e RUN_TIME=30s -e MAX_ORDERS=5 platform-demo/load-generator:local
```

In the workspace compose (profile `loadgen`, not started by `up.sh`; it places REAL orders and reviews): `docker compose -f local/compose.yaml --profile loadgen run --rm load-generator` (defaults there: USERS 3, SPAWN_RATE 1, RUN_TIME 30s, MAX_ORDERS 5, MAX_REVIEWS 3). Not run for this change.

## API

No API: there is no server. The tool is a client of the frontend's HTML routes. Its interface is the environment (next section), the exit code and the printed summary.

Exit code: 0 when the failure ratio is within `FAIL_RATIO`; 1 when it is above, or when no request was made; 2 for a bad configuration (message on stderr, before any request).

The journeys (full table with failure criteria: [`docs/api.md`](docs/api.md)); each simulated user is one visitor with its own cookie jar and tasks are picked by weight; a step that fails ends that journey:

| Journey (`JOURNEYS` name) | Weight | What it does |
|---|---|---|
| `browse` | 10 | home, a random department, a search (1 in 5 is a nonsense word), a sort, page 2 |
| `product_view` | 8 | product page, then one of its recommendations |
| `add_to_cart` | 4 | add an in-stock product, cart page, empty the cart |
| `checkout_success` | 3 | add, cart, checkout with the test card `4111111111111111` and the idempotency key read from the cart page (skipped once `MAX_ORDERS` is used up) |
| `checkout_declined` | 2 | checkout with `4000000000000002`, expects the clean 422 page |
| `out_of_stock` | 1 | add a sold-out product, expects 422 `out of stock` |
| `review` | 1 | post a review ("loadgen bot xxxxxx") on a random product (stops after `MAX_REVIEWS`) |
| `account` | 1 | register or sign in, one wrong-password attempt, `/account`, an order if the budget allows, order history, order page, mailbox poll for the confirmation mail, logout |

## Configuration

Every variable read by the code (`src/loadgen/config.py`, plus `LOADGEN_PASSWORD` in `journeys.py`; the only places that read the environment, checked 2026-11-14 with `grep -rn 'environ\|getenv' src/`). Bad values stop the run before any request with exit code 2.

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
| `LOADGEN_PASSWORD` | random per process | no | Password of the demo accounts the `account` journey registers (the shop accepts 8 to 72 bytes). Unset or empty: a random 22 character token (`secrets.token_urlsafe(16)`), different in every process. Read in `journeys.py`, not in `config.py` |
| `JOURNEYS` | all | no | Comma separated subset of the journey names (implemented with Locust tags); unknown names are an error |

Set by the Dockerfile, not by the code: `PYTHONPATH=/app/src`, `PYTHONUNBUFFERED=1`, `PYTHONDONTWRITEBYTECODE=1`. Locust itself reads `LOCUST_*` environment variables as defaults for its own options; the program passes all its options on the command line (`__main__.py`), so they are not relevant here (library behaviour, not tested).

The telemetry variables of the other services (`OTEL_*`, `PYROSCOPE_ADDR`, `LOG_LEVEL`) do not exist here: this tool has no telemetry code.

## Observability

What the tool emits today (code read 2026-11-13):

| Signal | Today | Not there |
|---|---|---|
| Traces | none. The requests carry no `traceparent`, so each request starts its own trace at the frontend | trace context from the load generator (OBS-60 would need it) |
| Metrics | none. Locust's statistics are printed once at the end | Prometheus / OTLP export of the run |
| Logs | Locust's own log lines and tables on stdout/stderr, plain text (not JSON); the `loadgen` logger for notes. No secrets: only demo accounts and the test cards of the shop | JSON logs, `trace_id` |
| Profiles | none | n/a for a batch tool |

The result is the printed summary after the Locust tables: requests, failures (and ratio), median/p95/p99, requests per second, orders placed, reviews posted, journeys run, failures by cause (short constant messages, so they group by cause) and a `PASSED` / `FAILED` verdict. Every response is also checked for leaked internals (`rpc error`, Go stack traces, password hashes). Static assets are not fetched, only the HTML pages. The standards' OBS rules were written for services; whether they apply to this batch tool is a question for the owner.

## Data

No database, no files written. A run leaves real demo data in the shop by design:

Real demo data in the stack, by design: placed orders (at most `MAX_ORDERS`, stock goes down by one each), their
confirmation mails, demo accounts `loadgen-<hex>@example.com` (one per simulated user and run), reviews by
`loadgen bot <hex>` (at most `MAX_REVIEWS`; they change the star averages of the products they hit). The compose
volumes are the only cleanup (`docker compose down -v`); nothing here deletes them.

## Develop

Requirements: Python 3.12 and [uv](https://github.com/astral-sh/uv). Layout: `src/loadgen/` (`__main__.py` env to Locust arguments, `config.py`, `journeys.py` Locust user and tasks, `client.py` checking client, `page.py` HTML helpers, `forms.py`, `budget.py`), `tests/` (with HTML fixtures saved from the running shop: trimmed, demo data only), `requirements.in` / `requirements.txt` (Locust 2.47.0 and its lock, compiled with `uv pip compile --python-version 3.12 --exclude-newer 2026-10-25`), `requirements-dev.txt` (pytest 9.1.1, ruff 0.17.2).

| Step | Command | Result on 2026-11-13 |
|---|---|---|
| Unit tests | `PYTHONPATH=src .venv/bin/pytest` (`pytest.ini` also sets `pythonpath`) | run, 44 passed |
| Lint | `.venv/bin/ruff check .` | run, all checks passed |
| Format | `.venv/bin/ruff format --check .` | run, 14 files already formatted |
| Security scan | `.venv/bin/bandit -r src/ -c pyproject.toml` (bandit 1.9.4, the version the shared pipeline installs) | run, exit 0, no issues with the `[tool.bandit]` skip B311 (reason in `pyproject.toml`). Without it: 10 findings (10 x B311 `random`); the former B105 skip is gone since the demo password is random per process (run 2026-11-14 with bandit 1.9.4) |
| Dependency audit | `pip-audit -r requirements.txt` | not run |
| Image | `docker build -t platform-demo/load-generator:local .` | not run today |
| Docs | `mkdocs build --strict` (mkdocs 1.6.1 + mkdocs-techdocs-core 1.7.1, Python 3.12 venv made with uv) | run, passed |

The tests run in a venv made with uv outside the repository (`uv venv --python 3.12`, `uv pip install -r requirements.txt -r requirements-dev.txt`).

Shared Python pipeline (`service-ci-python`) facts: it formats and lints with ruff, runs `pytest tests/`, `pip-audit -r requirements.txt` and `bandit -r src/ -c pyproject.toml`. Its default build-check file `src/server.py` does **not** exist in this repo (it is a client, not a server); the generated caller is expected to pass `src/loadgen/__main__.py` instead, which exists and parses (checked with `ast.parse`). That caller is not in this repo yet.

## Operate

- **Health:** none. There is no server, no port and no `HEALTHCHECK`; the exit code is the result.
- **Run length and shutdown:** the run ends after `RUN_TIME` (`--stop-timeout 30`: running tasks get up to 30 s to finish), prints the summary and exits with the code above. SIGTERM was tried on 2026-11-13 against a dead host (`HOST=http://127.0.0.1:1`, plain process, not the container): Locust logged `Shutting down`, printed its tables and exited (code 1 here, because every request had failed). `docker stop` of the image was not run.
- **Scaling:** one process, one Locust runner. Distributed Locust (master/workers) and the web UI are not used and were not run. The practical limit is the shop's capacity, which is unknown beyond the runs in `docs/development.md`; the caps `MAX_ORDERS` / `MAX_REVIEWS` protect stock and ratings.
- **Image:** `python:3.12-slim`, user `10001:10001`, nothing written to disk, no volume needed.
- Runbook: [`docs/operations.md`](docs/operations.md).

## Known limits

- It places real orders and reviews: stock goes down and star averages change; only `docker compose down -v` cleans up. Always keep the caps small against a shared stack.
- HTML only: static assets (images, CSS, JS) and the browser's JavaScript (Faro) are not exercised, so it is not a browser-realistic load.
- The shop's Secure session cookie is cleared by the client to make `python-requests` send it back over `http://` (see `docs/architecture.md`).
- No telemetry (see Observability); no trace context on requests.
- Not run: any run longer than 40 s, more than 5 users, or `MAX_ORDERS` above 5; runs against Kubernetes or any host other than the local compose stack; the review rate-limit path (HTTP 429) and the login rate limit; the compose profile `loadgen` for this change; `docker stop` of the image; arm64 build; `pip-audit`.

## License

Apache License 2.0, see [LICENSE](LICENSE).
