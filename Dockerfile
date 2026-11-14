# Base image: python:3.12-alpine, not -slim. Measured with Trivy 0.76.1 on 2026-11-14: python:3.12-slim (Debian 13.7) has 13 HIGH CVEs, 11 of
# them with NO Debian fix yet (util-linux, sqlite, ncurses, systemd libraries), so they could only be ignored. python:3.12-alpine
# (Alpine 3.24.4) had one vulnerable package (krb5-libs, fixed in 1.22.3-r0), and `apk upgrade` in the runtime stage installs the fix. So the
# scan passes by patching, without an ignore list. Rebuilding picks up newer Alpine fixes; the CI scan fails again if one is missing.

# ---- Build stage: dependencies from the fully pinned lock (requirements.in is its source; regenerate with uv pip compile) ----
FROM python:3.12-alpine AS builder

ENV PYTHONDONTWRITEBYTECODE=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /build
COPY requirements.txt .
RUN pip install --no-cache-dir --prefix=/install -r requirements.txt

# ---- Runtime stage ----
FROM python:3.12-alpine AS runtime

ARG SERVICE_VERSION=dev
ARG SERVICE_COMMIT=unknown

LABEL org.opencontainers.image.title="load-generator" \
      org.opencontainers.image.source="https://github.com/platform-boutique/app-load-generator" \
      org.opencontainers.image.revision="${SERVICE_COMMIT}" \
      org.opencontainers.image.version="${SERVICE_VERSION}" \
      org.opencontainers.image.licenses="Apache-2.0"

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app/src \
    SERVICE_VERSION=${SERVICE_VERSION} \
    SERVICE_COMMIT=${SERVICE_COMMIT}

# Patch the OS packages of the base image (fixes krb5-libs and anything else Alpine has fixed since the base image was built).
RUN apk upgrade --no-cache \
    && addgroup -S -g 10001 loadgen \
    && adduser -S -u 10001 -G loadgen -H -s /sbin/nologin loadgen

WORKDIR /app
COPY --from=builder /install /usr/local
COPY --chown=10001:10001 src/ ./src/

# Numeric so Kubernetes runAsNonRoot can verify it. Nothing is written to disk: no volume needed.
USER 10001:10001

# No port: the generator only makes outgoing requests (HOST). Settings are environment variables, see README.
# The default HOST is the compose service name of the frontend; RUN_TIME defaults to 60s, then the process exits.
ENTRYPOINT ["python", "-m", "loadgen"]
