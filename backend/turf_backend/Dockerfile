# ============================================================
# Stage 1: Builder — install dependencies into a virtual env
# Using a separate build stage keeps the final image lean by
# excluding pip, build tools, and cache layers.
# ============================================================
FROM python:3.12-slim AS builder

# Prevents Python from writing .pyc files to disc and
# ensures stdout/stderr are sent straight to the terminal (no buffering).
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

# Install system-level build dependencies needed by some Python packages
# (e.g., mysqlclient needs gcc and default-libmysqlclient-dev).
# These are only needed at build time; they won't appear in the final image.
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    default-libmysqlclient-dev \
    pkg-config \
    && rm -rf /var/lib/apt/lists/*

# Copy only requirements first to leverage Docker layer caching.
# As long as requirements.txt doesn't change, this layer is reused.
COPY requirements.txt .

# Install all Python dependencies into a dedicated virtual environment
# inside /app/venv so the final stage can copy just that folder.
RUN python -m venv /app/venv && \
    /app/venv/bin/pip install --upgrade pip --no-cache-dir && \
    /app/venv/bin/pip install --no-cache-dir -r requirements.txt


# ============================================================
# Stage 2: Runtime — final production image
# Only copies what's needed: the venv and the application code.
# ============================================================
FROM python:3.12-slim AS runtime

# Same Python hygiene flags as the builder
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

# Cloud Run injects PORT (default 8080); the app must respect it.
ENV PORT=8080

# Only the runtime shared library for mysqlclient is needed here
# (not the full dev headers / gcc).
RUN apt-get update && apt-get install -y --no-install-recommends \
    default-libmysqlclient-dev \
    && rm -rf /var/lib/apt/lists/*

# Create a non-root user for security best practices.
# Running as root inside a container is a security risk.
RUN addgroup --system appgroup && adduser --system --ingroup appgroup appuser

WORKDIR /app

# Copy the pre-built virtual environment from the builder stage.
COPY --from=builder /app/venv /app/venv

# Copy the Django project source code.
# The .dockerignore file prevents unwanted files (venv, .env, __pycache__, etc.)
# from being included.
COPY . .

# Collect static files so Django can serve them (or a CDN / whitenoise can).
# This requires DJANGO_SETTINGS_MODULE and SECRET_KEY to be resolvable.
# We use a placeholder SECRET_KEY here; the real one is injected at runtime.
RUN /app/venv/bin/python manage.py collectstatic --noinput \
    --settings=turf_backend.settings \
    || echo "collectstatic skipped (check STATIC_ROOT / DATABASE config)"

# Switch to the non-root user before starting the process.
RUN chown -R appuser:appgroup /app
USER appuser

# Inform Docker that the container listens on this port (documentation only).
EXPOSE 8080

# Activate the virtual environment by prepending its bin dir to PATH.
ENV PATH="/app/venv/bin:$PATH"

# Start Gunicorn:
#   --bind            : listen on all interfaces on $PORT (Cloud Run requirement)
#   --workers         : 2 × CPU cores + 1 is the Gunicorn rule of thumb;
#                       Cloud Run allocates 1 vCPU by default → 3 workers
#   --threads         : threads per worker for I/O-bound Django views
#   --timeout         : seconds before a worker is killed and restarted
#   --log-file        : send access/error logs to stdout for Cloud Logging
#   --access-logfile  : combined with --log-file for Cloud Logging visibility
CMD gunicorn \
    --bind 0.0.0.0:${PORT} \
    --workers 3 \
    --threads 2 \
    --timeout 120 \
    --log-level info \
    --log-file - \
    --access-logfile - \
    turf_backend.wsgi:application
