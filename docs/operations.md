# Operations

## Health

None. There is no server, no port and no `HEALTHCHECK`. The exit code is the result.

## Run and shutdown

- The run ends after `RUN_TIME`; running tasks get up to 30 s (`--stop-timeout 30`); the summary is printed and the process exits with 0, 1 or 2 (see [API](api.md)).
- SIGTERM, tried on 2026-11-13 against a dead host with the plain process: Locust logged `Shutting down`, printed its tables and exited (code 1 there, every request had failed). `docker stop` of the image was not run.

## Scaling

One process, one Locust runner. Distributed Locust and the web UI are not used. Keep `USERS` small against a shared stack: the shop's capacity under real load is unknown.

## What a run leaves behind

Real demo data in the stack, by design: placed orders (at most `MAX_ORDERS`, stock goes down by one each), their
confirmation mails, demo accounts `loadgen-<hex>@example.com` (one per simulated user and run), reviews by
`loadgen bot <hex>` (at most `MAX_REVIEWS`; they change the star averages of the products they hit). The compose
volumes are the only cleanup (`docker compose down -v`); nothing here deletes them.

## Runbook

| Symptom | Check |
|---|---|
| Exit code 2 | the message on stderr names the variable (`HOST`, `RUN_TIME`, `JOURNEYS`, ...) |
| Exit code 1, `no response` failures | `HOST` is wrong or the frontend is down; from a container use the compose network name or `--network host` |
| Exit code 1, `HTTP 302, expected 422` and similar | the shop changed behaviour or a product listed in `SOLD_OUT_PRODUCTS` is in stock; the summary groups failures by cause |
| Carts look empty, `/account` redirects | the Secure cookie handling in `client.py` (see architecture) |
| `checkout_success` never runs | `MAX_ORDERS` is used up or 0 |
