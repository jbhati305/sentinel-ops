from __future__ import annotations

import sqlite3
from typing import Any, Iterable, Protocol


class QueryExecutor(Protocol):
    def fetch_one(
        self,
        query: str,
        params: Iterable[Any] = (),
    ) -> sqlite3.Row | None:
        ...

    def fetch_all(
        self,
        query: str,
        params: Iterable[Any] = (),
    ) -> list[sqlite3.Row]:
        ...

    def execute(self, query: str, params: Iterable[Any] = ()) -> None:
        ...

    def scalar(self, query: str, params: Iterable[Any] = ()) -> Any:
        ...
