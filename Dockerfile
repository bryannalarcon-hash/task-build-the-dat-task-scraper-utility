# syntax=docker/dockerfile:1
# ---------------------------------------------------------------------------
# DAT Task Scraper — Docker image
# Base: python:3.11-slim with Tkinter and X11 support
# ---------------------------------------------------------------------------
FROM python:3.11-slim

# Install system packages needed for Tkinter + X11
RUN apt-get update && apt-get install -y --no-install-recommends \
        python3-tk \
        tk-dev \
        libx11-6 \
    && rm -rf /var/lib/apt/lists/*

# Create a non-root user so files written to the bind-mount are not root-owned
RUN useradd --create-home appuser
USER appuser

WORKDIR /workspace

# Install Python dependencies as the non-root user
COPY --chown=appuser:appuser requirements.txt /tmp/requirements.txt
RUN pip install --no-cache-dir --user -r /tmp/requirements.txt

# Copy application source files
COPY --chown=appuser:appuser scraper.py main.py ./

ENV PYTHONUNBUFFERED=1
# Ensure pip --user packages are on PATH
ENV PATH="/home/appuser/.local/bin:${PATH}"

ENTRYPOINT ["python", "main.py"]
