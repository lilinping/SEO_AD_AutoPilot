FROM python:3.9-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    curl \
    gnupg \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY apps/ apps/
COPY packages/ packages/
COPY .env.example .env

# Create necessary directories
RUN mkdir -p var/seo-ad-autopilot.db

# Expose port
EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8000/healthz || exit 1

# Run the application
CMD ["python", "-m", "uvicorn", "apps.api.seo_ad_autopilot.app:create_app", "--factory", "--host", "0.0.0.0", "--port", "8000"]
