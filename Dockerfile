FROM python:3.10-slim

WORKDIR /app

# Install system dependencies
# build-essential for some python packages, headers
RUN apt-get update && apt-get install -y build-essential curl && rm -rf /var/lib/apt/lists/*

# Copy requirements first for caching
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy source code
COPY backend ./backend
COPY ingestion ./ingestion
# Copy config/env if needed, or pass as ENV vars
# We skip .env for security, inject variables at runtime

# Create vector store directory
RUN mkdir -p vector_store

# Uploaded/ingested data should be mounted or copied
# For this image, we might assume ingestion happens at build or run time.
# Let's copy the ingestion scripts.

# Expose port
EXPOSE 8000

# Run Uvicorn
CMD ["uvicorn", "backend.main:app", "--host", "0.0.0.0", "--port", "8000"]
