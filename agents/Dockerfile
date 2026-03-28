# Use the official crawl4ai image as base
FROM unclecode/crawl4ai:latest

# Install uv package manager
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

WORKDIR /app

# Copy dependency files first for better caching
COPY pyproject.toml README.md ./

# Create virtual environment inside /app (recommended location)
RUN uv venv --system-site-packages /app/.venv

# Set environment variables for the virtual environment
ENV VIRTUAL_ENV=/app/.venv
ENV PATH="/app/.venv/bin:$PATH"

# Install project dependencies
RUN uv pip compile pyproject.toml -o requirements.txt && \
    uv pip install -r requirements.txt

# Install Playwright browsers (requires root)
USER root
RUN /app/.venv/bin/python -m playwright install chromium --with-deps

# Fix permissions for the existing 'appuser' (already present in base image)
RUN chown -R appuser:appuser /app

# Switch to non-root user
USER appuser

# Copy the rest of the application code with correct ownership
COPY --chown=appuser:appuser . .

EXPOSE 8001

# Start uvicorn using the venv's python (with --reload for development)
CMD ["/app/.venv/bin/python", "-m", "uvicorn", "server:app", "--host", "0.0.0.0", "--port", "8001", "--reload", "--log-level", "info"]