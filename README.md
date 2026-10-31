# load-generator

A small [Locust](https://locust.io) project that drives the Everly storefront (the `frontend` service) with
weighted, realistic visitor journeys and prints a summary. It speaks HTTP to the frontend only (no gRPC, no direct
calls to other services) and never contacts anything except `HOST`.

It is a test client for the local compose stack: it places real (demo) orders, registers demo accounts and posts a
few demo reviews, so it has hard caps (`MAX_ORDERS`, `MAX_REVIEWS`) and is polite by default (5 users, spawn rate 1,
1 to 3 s think time between journeys).

## Journeys

Each simulated user is one visitor with its own cookie jar. Tasks are picked by weight; a step that fails ends that
journey (no cascade of follow-up failures).

| Journey (`JOURNEYS` name) | Weight | What it does | What counts as a failure |
|---|---|---|---|
| `browse` | 10 | home, a random department, a search (a tag seen on product pages; 1 in 5 is a nonsense word), a sort, page 2 of the catalog | not 200, brand `Everly` missing, a page without product cards, `Nothing found` missing for the nonsense search |
| `product_view` | 8 | product page, then one of its recommendations | not 200, add-to-cart form or `Customer reviews` missing, **no recommendations block** |
| `add_to_cart` | 4 | pick an in-stock product, add it, cart page, empty the cart, check the cart is empty | add is not 302 to `/cart`, cart lacks the product or the `idempotency_key`, cart not empty afterwards |
| `checkout_success` | 3 | add, cart, checkout with `4111111111111111` using the **idempotency key read from the rendered cart page** | not 200, `Your order is complete` or the confirmation id missing. Skipped once `MAX_ORDERS` is used up |
| `checkout_declined` | 2 | add, cart, checkout with `4000000000000002`, empty the cart | not the clean 422 page (`We could not process that`, `declined`, link back to the cart), or the order-complete page appears |
| `out_of_stock` | 1 | add a sold-out product (default `volleyball-153`, stock 0 in the catalog seed) | not 422 with `out of stock` |
| `review` | 1 | post a review ("loadgen bot xxxxxx", random 1 to 5 stars) on a random product | not 303 back to the product, `your review has been posted` missing. Stops after `MAX_REVIEWS` |
| `account` | 1 | register (once per simulated user) or sign in, one wrong-password attempt (once per user), `/account`, an order if the budget allows, then order history, order page, **mailbox poll for the confirmation mail** (up to 20 x 1 s) and the mail page (sandboxed iframe), logout | wrong status or marker anywhere, `Wrong email or password` missing on the 422, the order missing in the history, the mail never arriving |

Every response is also checked for leaked internals (`rpc error`, Go stack traces, password hashes). Redirects are
never followed automatically; a journey follows only the ones it expects, and only to the same host. Static assets
(images, CSS, JS) are not fetched, only the HTML pages.

Product choice for carts: the generator only buys products whose page says plainly `In stock` (not `Only N left`,
not sold out), so a run does not take the last units of anything. Failed requests are named with a short constant
message, so the summary groups them by cause.

Cookies: the frontend marks its cookies `Secure`; `python-requests` would not send them back over `http://`, which
would turn every request into a new visitor. The client clears the flag on received cookies (see `client.py`).

## Environment

| Variable | Default | Meaning |
|---|---|---|
| `HOST` | `http://frontend:8080` | Base URL of the frontend (scheme, host, port, no path). The only host contacted |
| `USERS` | `5` | Simulated users |
| `SPAWN_RATE` | `1` | Users started per second |
| `RUN_TIME` | `60s` | Run length (`30s`, `5m`, `1h30m`); the process exits afterwards |
| `MAX_ORDERS` | `30` | Hard cap of successful checkouts per run (all journeys together). `0` = place no orders |
| `MAX_REVIEWS` | `10` | Hard cap of posted reviews per run. `0` = post none |
| `FAIL_RATIO` | `0.01` | Exit code 1 when failed / total requests is above this (0 to 1). Also exit 1 when no request was made |
| `THINK_MIN`, `THINK_MAX` | `1`, `3` | Seconds a user waits between journeys (random in between) |
| `SOLD_OUT_PRODUCTS` | `volleyball-153` | Comma separated product ids with stock 0, used by `out_of_stock` |
| `JOURNEYS` | all | Comma separated subset of the journey names above (implemented with Locust tags) |

Bad values stop the run before any request with exit code 2 and a message. The run is headless
(`locust --headless --only-summary`): no web UI, no port.

Exit code: 0 when the failure ratio is within `FAIL_RATIO`, 1 otherwise. After the Locust tables the generator prints
its own summary (requests, failures, median/p95/p99, orders placed, journeys run, failures by cause).

## Run it

Locally, against the compose stack in `local/` (shop at http://localhost:8080):

```bash
uv venv --python 3.12 .venv
uv pip install --python .venv/bin/python -r requirements.txt -r requirements-dev.txt
HOST=http://localhost:8080 USERS=5 SPAWN_RATE=1 RUN_TIME=30s MAX_ORDERS=5 PYTHONPATH=src .venv/bin/python -m loadgen
```

As a container (the image has no port and runs as UID 10001; use `--network host` to reach a published port on the
host, or the compose network and `HOST=http://frontend:8080`):

```bash
docker build -t load-generator:local .
docker run --rm --network host -e HOST=http://localhost:8080 -e RUN_TIME=30s -e MAX_ORDERS=5 load-generator:local
```

In compose (profile `loadgen`, not started by default): the integrator adds a service that builds this directory,
sets `profiles: ["loadgen"]`, `depends_on` the frontend (healthy) and takes the variables above. Then
`docker compose --profile loadgen run --rm load-generator`. This wiring is not part of this repo and was **not run**.

Tests and lint:

```bash
PYTHONPATH=src .venv/bin/pytest          # or just .venv/bin/pytest (pytest.ini sets pythonpath)
.venv/bin/ruff check . && .venv/bin/ruff format --check .
```

The unit tests cover the HTML helpers (product ids, pager, tags, stock state, recommendations, idempotency key,
order id, mailbox, error pages, same-host check) against pages saved from the running shop in `tests/fixtures`
(trimmed: head, scripts, SVG and CSS removed, the session id in the footer replaced; demo data only), the config
parsing, the caps, and the checking client (`Visitor`) against a tiny local HTTP server (statuses, markers, leaks,
redirects, Secure cookies).

## What a run leaves behind

Real demo data in the stack, by design: placed orders (at most `MAX_ORDERS`, stock goes down by one each), their
confirmation mails, demo accounts `loadgen-<hex>@example.com` (one per simulated user and run), reviews by
`loadgen bot <hex>` (at most `MAX_REVIEWS`; they change the star averages of the products they hit). The compose
volumes are the only cleanup (`docker compose down -v`); nothing here deletes them.

## Layout

```
src/loadgen/__main__.py   env -> locust arguments, exit code 2 on bad config
src/loadgen/config.py     environment parsing and validation
src/loadgen/journeys.py   Locust user, weighted tasks, caps, summary, FAIL_RATIO exit code
src/loadgen/client.py     Visitor: request + status/marker/leak/redirect checks, Secure-cookie handling
src/loadgen/page.py       HTML helpers and the marker strings (pure functions, unit tested)
src/loadgen/forms.py      form payloads (field names of the frontend templates)
src/loadgen/budget.py     the MAX_ORDERS / MAX_REVIEWS counters
requirements.in / .txt    locust 2.47.0 and its pinned lock (uv pip compile --python-version 3.12 --exclude-newer 2026-10-25)
```

Dependencies: Locust 2.47.0 (released 2026-10-21, the newest release at least 7 days old when this was written; the
lock is compiled with `--exclude-newer` so every transitive pin is old enough too). Dev only: pytest 9.1.1, ruff 0.17.2.

## Results of the real runs (2026-11-01, local stack, WSL2)

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

## What was NOT run

- The compose service and profile `loadgen` (not in this repo; the image was only started with `docker run`).
- Any run longer than 40 s, more than 5 users, or a run with `MAX_ORDERS` above 5 (the shop's checkout capacity under
  real load is unknown).
- Runs against Kubernetes or any host other than the local compose stack; the image was never pushed or signed.
- The review journey's rate-limit path (`REVIEW_RATE_LIMIT`, HTTP 429) and the login rate limit were not provoked.
- Distributed Locust (master/workers) and the Locust web UI.
