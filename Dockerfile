# ---------------------------------------------------------------------------
# ACEest Fitness & Gym - multi-stage image
#   builder : installs runtime deps into an isolated virtualenv
#   test    : builder + dev deps + tests  -> used by CI/Jenkins to run Pytest
#   runtime : slim, non-root, production image (default target)
# ---------------------------------------------------------------------------
ARG PYTHON_VERSION=3.12

FROM python:${PYTHON_VERSION}-slim AS base
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PATH="/opt/venv/bin:${PATH}"
WORKDIR /app

# ---------- builder ----------
FROM base AS builder
RUN python -m venv /opt/venv
# Copy only the requirements first so this layer is cached between code changes
COPY requirements.txt .
RUN pip install -r requirements.txt

# ---------- test ----------
FROM builder AS test
COPY requirements-dev.txt .
RUN pip install -r requirements-dev.txt
COPY pytest.ini .flake8 app.py ./
COPY aceest/ aceest/
COPY templates/ templates/
COPY static/ static/
COPY tests/ tests/
CMD ["pytest", "-v", "--cov=app", "--cov=aceest", "--cov-report=term-missing"]

# ---------- runtime ----------
FROM base AS runtime
LABEL org.opencontainers.image.title="aceest-fitness" \
      org.opencontainers.image.description="ACEest Fitness & Gym Flask service" \
      org.opencontainers.image.authors="Bandgar Omkar Sudhakar Sheetal (2025TM93075)"

# Unprivileged user; only the data directory is writable by it
RUN groupadd --system --gid 10001 aceest \
 && useradd --system --uid 10001 --gid aceest --home-dir /app --shell /usr/sbin/nologin aceest \
 && mkdir -p /app/instance \
 && chown aceest:aceest /app/instance

COPY --from=builder /opt/venv /opt/venv
COPY app.py ./
COPY aceest/ aceest/
COPY templates/ templates/
COPY static/ static/

ENV DATABASE_PATH=/app/instance/aceest_fitness.db \
    PORT=5000
USER 10001:10001
EXPOSE 5000
VOLUME ["/app/instance"]

HEALTHCHECK --interval=30s --timeout=3s --start-period=10s --retries=3 \
  CMD ["python", "-c", "import urllib.request; urllib.request.urlopen('http://127.0.0.1:5000/health', timeout=2)"]

CMD ["gunicorn", "--bind", "0.0.0.0:5000", "--workers", "2", "--access-logfile", "-", "app:create_app()"]
