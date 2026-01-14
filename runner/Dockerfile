FROM python:3.11-slim

# Basic build deps for common wheels
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
 && rm -rf /var/lib/apt/lists/*

# Common research stack (add/remove as you like)
RUN pip install --no-cache-dir \
    numpy pandas pyarrow matplotlib scipy scikit-learn

# Create non-root user
RUN useradd -m -u 10001 runner
USER runner

WORKDIR /work
CMD ["python", "main.py"]
