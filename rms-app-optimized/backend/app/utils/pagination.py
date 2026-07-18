"""Pagination helpers (INV-11: default limit 20, max 100)."""
from __future__ import annotations

from dataclasses import dataclass

DEFAULT_LIMIT = 20
MAX_LIMIT = 100


@dataclass(frozen=True)
class Page:
    page: int
    limit: int

    @property
    def offset(self) -> int:
        return (self.page - 1) * self.limit


def resolve(page: int = 1, limit: int = DEFAULT_LIMIT) -> Page:
    page = max(1, page)
    limit = max(1, min(limit, MAX_LIMIT))
    return Page(page=page, limit=limit)


def meta(page: Page, total: int) -> dict:
    return {"page": page.page, "limit": page.limit, "total": total}
