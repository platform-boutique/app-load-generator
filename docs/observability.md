# Observability

What the tool emits today (code read 2026-11-13):

| Signal | Today | Not there |
|---|---|---|
| Traces | none. The requests carry no `traceparent`, so each request starts its own trace at the frontend | trace context from the load generator (OBS-60 would need it) |
| Metrics | none. Locust's statistics are printed once at the end | Prometheus / OTLP export of the run |
| Logs | Locust's own log lines and tables on stdout/stderr, plain text (not JSON); the `loadgen` logger for notes. No secrets: only demo accounts and the test cards of the shop | JSON logs, `trace_id` |
| Profiles | none | n/a for a batch tool |

The result is the printed summary after the Locust tables: requests, failures (and ratio), median/p95/p99, requests per second, orders placed, reviews posted, journeys run, failures by cause (short constant messages, so they group by cause) and a `PASSED` / `FAILED` verdict. Every response is also checked for leaked internals (`rpc error`, Go stack traces, password hashes). Static assets are not fetched, only the HTML pages. The standards' OBS rules were written for services; whether they apply to this batch tool is a question for the owner.
