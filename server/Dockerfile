FROM python:3.12-slim

RUN pip install --no-cache-dir uv==0.8.13

WORKDIR /code
COPY pyproject.toml uv.lock* ./
COPY app ./app
RUN uv sync --frozen --no-dev

# Cloud Run sends traffic to $PORT (default 8080); bind to all interfaces.
ENV MCP_HOST=0.0.0.0 MCP_PORT=8080
EXPOSE 8080
CMD ["uv", "run", "--no-dev", "python", "-m", "app"]
