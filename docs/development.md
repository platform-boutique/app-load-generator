# Develop and test

Requirements: Python 3.12 and uv. Layout and commands: see the README, section Develop.

Commands run on 2026-11-13 for the standards change (venv made with uv, Python 3.12):

| Command | Result |
|---|---|
| `PYTHONPATH=src pytest` (venv from `requirements.txt` + `requirements-dev.txt`, Python 3.12 via uv) | 56 passed (re-run 2026-11-21 on `origin/main`) |
| `ruff check .` / `ruff format --check .` (ruff 0.17.2) | all checks passed / 27 files already formatted (re-run 2026-11-21) |
| `bandit -r src/ -c pyproject.toml` (bandit 1.9.4) | exit 0, no issues (with the `[tool.bandit]` skip B311); without it 10 findings (B311) |
| `mkdocs build --strict` (mkdocs 1.6.1, mkdocs-techdocs-core 1.7.1, Python 3.12 venv made with uv) | passed |

## What the earlier author ran (recorded, not re-run for this page)

The runs below come from the README before the standards change; they were not repeated on 2026-11-13.

Run on 2026-11-01 by the author, local stack (WSL2); not repeated on 2026-11-13:

Real short run against the running compose stack, from the venv:

```
HOST=http://localhost:8080 USERS=5 SPAWN_RATE=1 RUN_TIME=30s MAX_ORDERS=5 python -m loadgen
```

| | |
|---|---|
| requests | 240 |
| failures | 0 (0.00 %) |
| response time | median 17 ms, p95 43 ms, p99 79 ms |
| throughput | 9.0 requests/s |
| orders placed | 5 (cap reached) |
| journeys | browse 21, product_view 17, add_to_cart 15, checkout_success 5, checkout_declined 1, out_of_stock 2, review 1 |
| exit code | 0 |

The `account` journey did not come up in that run (weight 1, random). It was run on its own with
`JOURNEYS=account USERS=2 RUN_TIME=40s MAX_ORDERS=2`: 190 requests, 0 failures, 2 orders, both confirmation mails
found on the first poll, exit 0. Other runs: a 25 s run with 2 users (96 requests, 0 failures), and
`docker run --network host` of the built image for 20 s with 3 users and a subset of journeys (78 requests,
0 failures, exit 0). Timings come from a WSL2 host whose wall clock jumps, so the millisecond numbers are indicative only.

Failure detection was checked on purpose: a dead host gives exit 1 (`no response` failures); declaring an in-stock
product as sold out (`SOLD_OUT_PRODUCTS=american-football-137 JOURNEYS=out_of_stock`) gives
`HTTP 302, expected 422`, ratio 0.8, exit 1. Unit tests cover marker failures, unexpected statuses, leaks and
foreign redirects.

An early run of the first version failed 4 of 62 requests because the Secure session cookie was not sent back (carts
looked empty, `/account` redirected). That was a bug in this client, fixed (see Cookies above), not a shop problem.

### What the author did NOT run

- The compose service and profile `loadgen` (not in this repo; the image was only started with `docker run`).
- Any run longer than 40 s, more than 5 users, or a run with `MAX_ORDERS` above 5 (the shop's checkout capacity under
  real load is unknown).
- Runs against Kubernetes or any host other than the local compose stack; the image was never pushed or signed.
- The review journey's rate-limit path (`REVIEW_RATE_LIMIT`, HTTP 429) and the login rate limit were not provoked.
- Distributed Locust (master/workers) and the Locust web UI.

## Build the docs

```bash
uv venv docs-venv && uv pip install --python docs-venv/bin/python 'mkdocs==1.6.1' 'mkdocs-techdocs-core==1.7.1'
docs-venv/bin/mkdocs build --strict
```

Mermaid diagrams are plain fenced code blocks for `mkdocs`; rendering them in Backstage needs the TechDocs Mermaid add-on (not verified here).
