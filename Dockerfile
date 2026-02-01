FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

# Install minimal build deps for some packages that may need compilation
RUN apt-get update \
    && apt-get install -y --no-install-recommends build-essential git \
    && rm -rf /var/lib/apt/lists/*

# Copy only requirements first to leverage layer caching
COPY requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt

# Copy project
COPY . /app

# Create a persistent state directory
RUN mkdir -p /app/state && chown -R root:root /app/state
VOLUME ["/app/state"]

ENV STATE_DB=/app/state/portfolio.db

# Default command runs the multi-pair demo; override in compose or CLI
CMD ["python", "examples/demo_multi_pair.py"]
