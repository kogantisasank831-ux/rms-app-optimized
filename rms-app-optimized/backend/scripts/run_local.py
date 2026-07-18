"""Local dev launcher (Windows-friendly).

asyncpg requires the SelectorEventLoop on Windows; the Docker/Linux runtime uses uvicorn
directly (see docker-compose) and does not need this shim.

Run from backend/:  python scripts/run_local.py
"""
from __future__ import annotations

import asyncio
import os
import sys

# Make the backend dir importable no matter where this script is launched from
# (so `app.main:app` resolves without needing PYTHONPATH set).
_BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _BACKEND_DIR not in sys.path:
    sys.path.insert(0, _BACKEND_DIR)

if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

import uvicorn  # noqa: E402

if __name__ == "__main__":
    uvicorn.run(
        "app.main:app",
        host=os.getenv("HOST", "127.0.0.1"),
        port=int(os.getenv("PORT", "8000")),
        log_level="info",
    )
