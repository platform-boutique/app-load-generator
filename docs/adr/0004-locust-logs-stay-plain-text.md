# 4. Locust's own output stays plain text; this program's lines are JSON

Status: accepted (owner decision, 2026-11-22).

## Context

OBS-30 asks every service for JSON logs in the standard shape with trace ids. The load generator is a batch client, not a service: it has no port, no traces to correlate (it starts them) and it prints Locust's own progress lines and summary tables, which come from a third-party library.

## Decision

The lines written by this program are JSON in the standard shape: the `starting` line (version, commit, host, users, run time, request timeout) on stdout and the bad-configuration error (exit code 2) on stderr. Locust's own log lines and the printed summary stay plain text; they are meant to be read by a person at the end of a run and the verdict is the exit code.

## Consequences

- A log pipeline that parses this container's stdout as JSON must tolerate the plain-text Locust lines (not tested with the local stack's pipeline).
- No request_id or trace_id field in those lines. Requests to the frontend carry no trace context from here; the frontend starts its own traces.
- Revisit only if the generator ever runs as a long-lived service.
