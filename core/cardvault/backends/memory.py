"""memory 后端：对 ``index.build()`` 产物 dict 的薄封装（M0 语义原样保留）。"""

from __future__ import annotations

from typing import Any


class MemoryIndexBackend:
    name = "memory"

    def __init__(self, idx: dict[str, Any]) -> None:
        self._catalog: dict[str, Any] = idx["catalog"]
        self._aliases: dict[str, list[str]] = idx["aliases"]
        self._links: dict[str, dict[str, list[dict[str, str]]]] = idx["links"]
        self._inverted: dict[str, dict[str, int]] = idx["inverted"]
        self._meta: dict[str, Any] = idx["meta"]

    def entry(self, card_id: str) -> dict[str, Any] | None:
        return self._catalog.get(card_id)

    def alias_ids(self, key: str) -> list[str]:
        return list(self._aliases.get(key, []))

    def alias_keys(self) -> list[str]:
        return list(self._aliases)

    def postings(self, tokens: list[str]) -> dict[str, dict[str, int]]:
        return {t: dict(self._inverted[t]) for t in tokens if t in self._inverted}

    def doc_stats(self) -> tuple[int, float]:
        return int(self._meta["cards"]), float(self._meta["avgdl"])

    def doclen(self, card_id: str) -> int:
        return int(self._meta["doclen"].get(card_id, 0))

    def links(self, card_id: str) -> dict[str, list[dict[str, str]]]:
        return {
            "out": list(self._links["out"].get(card_id, [])),
            "in": list(self._links["in"].get(card_id, [])),
        }
