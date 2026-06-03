# Stage 1: Build the Vite + React dashboard
FROM node:20-slim AS dashboard-builder

WORKDIR /build/dashboard
COPY dashboard/package.json dashboard/package-lock.json ./
RUN npm ci

COPY dashboard/ ./
RUN npm run build

# Stage 2: Python proxy
FROM python:3.12-slim

WORKDIR /app

# Install Python dependencies
COPY pyproject.toml ./
RUN pip install --no-cache-dir -e .

# Copy proxy source
COPY proxy/ ./proxy/

# Copy compiled dashboard from Stage 1
COPY --from=dashboard-builder /build/dashboard/dist ./dashboard/dist

# Create directory for the SQLite DB (operator mounts a volume here)
RUN mkdir -p /data

ENV RELAY_DB_PATH=/data/relay.db

EXPOSE 8000

CMD ["uvicorn", "proxy.main:app", "--host", "0.0.0.0", "--port", "8000"]
