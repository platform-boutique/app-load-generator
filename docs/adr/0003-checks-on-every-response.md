# 3. Every response is checked; the exit code carries the verdict

Status: accepted (reconstructed from the code and the earlier README).

## Context

A load tool that only measures latency hides broken pages.

## Decision

Each step checks the status, marker strings of the page and the absence of leaked internals (`rpc error`, Go stack traces, password hashes). A failed step ends that journey (no cascade). Failed requests get short constant names so the summary groups them by cause. The process exits 1 when the failure ratio is above `FAIL_RATIO` (default 1 %) or when no request was made.

## Consequences

- A run doubles as a smoke test of the user-visible flows.
- Markers depend on the frontend's wording: a copy change in a template can fail a journey (the unit tests use saved pages as fixtures).
