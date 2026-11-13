# 1. Locust, headless, HTML journeys against the frontend only

Status: accepted (reconstructed from the code and the earlier README; no dated decision record existed).

## Context

The shop needs a repeatable way to produce realistic traffic for the local stack (and later for the observability work) without a browser farm.

## Decision

Use Locust as the engine, started headless by `python -m loadgen` with the settings from environment variables, and drive the frontend's HTML pages with weighted visitor journeys. No gRPC, no direct calls to other services; the only host contacted is `HOST`.

## Consequences

- Cheap to run, one process, no UI port.
- HTML only: static assets and browser JavaScript are not exercised.
- Requests carry no trace context.
- The result is a printed summary and an exit code, which can gate a script or a pipeline step.
