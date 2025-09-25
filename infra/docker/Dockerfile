FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /app

# System deps for build
RUN apt-get update && apt-get install -y --no-install-recommends build-essential && rm -rf /var/lib/apt/lists/*

# Copy and install
COPY pyproject.toml ./
COPY src ./src
RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir "uvicorn>=0.30" "redis>=5.0.4" "starlette>=0.37" "mcp[cli]>=1.9.0" "pydantic-settings>=2.3" \
    && pip install -e .

EXPOSE 8000
ENV REDIS_URL=redis://redis:6379/0
#CMD ["uvicorn", "prynai_mcp.app:app", "--host", "0.0.0.0", "--port", "8000", "--lifespan", "on"]

# infra/docker/Dockerfile (replace CMD)
EXPOSE 8000 8443
CMD ["sh", "-lc", "\
    if [ -n \"$SSL_CERTFILE\" ] && [ -n \"$SSL_KEYFILE\" ]; then \
    uvicorn prynai_mcp.app:app --host 0.0.0.0 --port 8443 --lifespan on --ssl-certfile $SSL_CERTFILE --ssl-keyfile $SSL_KEYFILE; \
    else \
    uvicorn prynai_mcp.app:app --host 0.0.0.0 --port 8000 --lifespan on; \
    fi"]
