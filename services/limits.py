# services/limits.py
from __future__ import annotations

import os

# Strategy/code size limits
MAX_STRATEGY_NAME_LEN = int(os.getenv("MAX_STRATEGY_NAME_LEN", "80"))
MAX_STRATEGY_DESC_LEN = int(os.getenv("MAX_STRATEGY_DESC_LEN", "400"))
MAX_ENTRYPOINT_LEN = int(os.getenv("MAX_ENTRYPOINT_LEN", "120"))

MAX_FILE_BYTES = int(os.getenv("MAX_FILE_BYTES", str(200_000)))          # per file
MAX_TOTAL_FILES = int(os.getenv("MAX_TOTAL_FILES", "25"))               # total files per strategy
MAX_TOTAL_BYTES = int(os.getenv("MAX_TOTAL_BYTES", str(2_000_000)))      # all files per strategy

# Run limits
MAX_SYMBOLS = int(os.getenv("MAX_SYMBOLS", "25"))
MAX_TIMEOUT_SEC = int(os.getenv("MAX_TIMEOUT_SEC", "60"))
MAX_LOOKBACK_DAYS = int(os.getenv("MAX_LOOKBACK_DAYS", "3650"))          # 10y default
