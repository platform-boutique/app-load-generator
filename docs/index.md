# load-generator

A small Locust project that drives the Everly storefront (the `frontend` service) with weighted, realistic visitor journeys and prints a summary. A batch tool: HTTP to the frontend only, runs for `RUN_TIME` and exits.

- It places real (demo) orders, registers demo accounts and posts a few demo reviews, so it has hard caps (`MAX_ORDERS`, `MAX_REVIEWS`).
- The exit code is the verdict: 0 within `FAIL_RATIO`, 1 above it, 2 for a bad configuration.

| | |
|---|---|
| Runtime | Python 3.12, Locust 2.47.0, image `platform-demo/load-generator:local` (built locally only) |
| Ports | none |
| State | none; leaves demo data in the shop |
| Depends on | frontend (HTTP) |
| Status | not deployed anywhere; no pipeline |

Pages: [architecture](architecture.md), [journeys](api.md), [configuration](configuration.md), [observability](observability.md), [operations](operations.md), [development](development.md), [decisions](adr/0001-locust-headless-html-journeys.md).
