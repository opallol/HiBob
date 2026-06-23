FROM python:3.11-slim

WORKDIR /app

# System deps kept minimal; asyncpg ships wheels.
COPY pyproject.toml ./
RUN pip install --no-cache-dir \
    "fastapi>=0.115" "uvicorn[standard]>=0.32" "httpx>=0.27" "asyncpg>=0.30" \
    "pydantic>=2.9" "pydantic-settings>=2.6" "anthropic>=0.40" \
    "qdrant-client>=1.12" \
    "opentelemetry-sdk>=1.29" "opentelemetry-exporter-otlp-proto-grpc>=1.29"

COPY hibob_core ./hibob_core

EXPOSE 8088
CMD ["uvicorn", "hibob_core.api.app:app", "--host", "0.0.0.0", "--port", "8088"]
