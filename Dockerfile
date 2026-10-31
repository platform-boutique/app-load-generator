# ---- Build stage: dependencies from the fully pinned lock (requirements.in is its source; regenerate with uv pip compile) ----
FROM python:3.12-slim AS builder

ENV PYTHONDONTWRITEBYTECODE=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /build
COPY requirements.txt .
RUN pip install --no-cache-dir --prefix=/install -r requirements.txt

# ---- Runtime stage ----
FROM python:3.12-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app/src

RUN groupadd --system --gid 10001 loadgen \
    && useradd --system --uid 10001 --gid loadgen --no-create-home --shell /usr/sbin/nologin loadgen

WORKDIR /app
COPY --from=builder /install /usr/local
COPY --chown=10001:10001 src/ ./src/

# Numeric so Kubernetes runAsNonRoot can verify it. Nothing is written to disk: no volume needed.
USER 10001:10001

# No port: the generator only makes outgoing requests (HOST). Settings are environment variables, see README.
# The default HOST is the compose service name of the frontend; RUN_TIME defaults to 60s, then the process exits.
ENTRYPOINT ["python", "-m", "loadgen"]
