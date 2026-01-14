#!/usr/bin/env bash
set -euo pipefail

# Runner contract:
# - workspace mounted at /work
# - user entry script passed as args, e.g. python main.py
# - artifacts written to /work/artifacts
# - data available at /work/data

cd /work

# Ensure expected dirs exist
mkdir -p /work/artifacts /work/data

# Conservative defaults
export PYTHONDONTWRITEBYTECODE=1
export PYTHONUNBUFFERED=1

# If ulimit is supported in your environment, you can uncomment:
# ulimit -t 30            # CPU seconds
# ulimit -v 800000        # virtual memory KB (approx)
# ulimit -n 256           # open files

exec "$@"
