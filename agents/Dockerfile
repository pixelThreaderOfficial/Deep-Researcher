# Use the official crawl4ai image as the base, which pre-configures
# Playwright, Chromium, and crawl4ai dependencies.
FROM unclecode/crawl4ai:latest

# Ensure python 3.12 is explicitly available if needed, though the base image configures Python for us.
# Install the uv package manager from the official Astral image for super fast installs
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

# Set working directory inside the container
WORKDIR /app

# Copy dependency definition files first to leverage Docker layer caching
COPY pyproject.toml README.md ./

# Create a virtual environment that inherits the pre-installed crawl4ai system packages safely
RUN uv venv --system-site-packages .venv
ENV PATH="/app/.venv/bin:$PATH"

# Extract dependencies and install them directly into the isolated virtual environment
RUN uv pip compile pyproject.toml -o requirements.txt && uv pip install -r requirements.txt

# Copy the rest of the application codebase
COPY . .

# Expose the new port that FastAPI will run on
EXPOSE 8001

# Start the server using the virtual environment's python directly to ensure it sees all our dependencies
CMD ["/app/.venv/bin/python", "-m", "uvicorn", "server:app", "--host", "0.0.0.0", "--port", "8001"]
