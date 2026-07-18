"""Test bootstrap.

On Windows, asyncpg requires the SelectorEventLoop (the default ProactorEventLoop raises
WinError 121 on socket connect). Production runs on Linux in Docker, so this is local-only.
Must run before any event loop is created — hence at conftest import time.
"""
from __future__ import annotations

import asyncio
import os
import sys

# pytest-asyncio (auto mode) uses a fresh event loop per test; the app engine must therefore
# use NullPool so an asyncpg connection is never reused across a closed loop ("Event loop is
# closed" on teardown). session.py switches to NullPool when APP_ENV=test — set it before any
# app import so the cached settings pick it up.
os.environ.setdefault("APP_ENV", "test")

if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
