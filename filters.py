from __future__ import annotations

import re
from collections import Counter
from typing import Any, Dict, List, Optional

from logger import get_logger

log = get_logger(__name__)

HeadlineRow = Dict[str, Any]


class HeadlineFilter:
    def __init__(self, headlines: List[HeadlineRow]) -> None:
        self._data: List[HeadlineRow] = list(headlines)
        self._original_count: int = len(headlines)

    def keyword(self, term: str) -> "HeadlineFilter":
        if not term or not term.strip():
            return self
        pattern = re.compile(re.escape(term.strip()), re.IGNORECASE)
        self._data = [h for h in self._data if pattern.search(h.get("title", ""))]
        return self

    def keyword_in_any(self, term: str) -> "HeadlineFilter":
        if not term or not term.strip():
            return self
        pattern = re.compile(re.escape(term.strip()), re.IGNORECASE)
        fields = ("title", "source", "author", "category")
        self._data = [
            h for h in self._data
            if any(pattern.search(str(h.get(f, ""))) for f in fields)
        ]
        return self

    def by_source(self, source: str) -> "HeadlineFilter":
        if not source:
            return self
        self._data = [h for h in self._data if h.get("source") == source]
        return self

    def by_sources(self, sources: List[str]) -> "HeadlineFilter":
        if not sources:
            return self
        source_set = set(sources)
        self._data = [h for h in self._data if h.get("source") in source_set]
        return self

    def by_category(self, category: str) -> "HeadlineFilter":
        if not category:
            return self
        self._data = [h for h in self._data if h.get("category") == category]
        return self

    def by_categories(self, categories: List[str]) -> "HeadlineFilter":
        if not categories:
            return self
        cat_set = set(categories)
        self._data = [h for h in self._data if h.get("category") in cat_set]
        return self

    def by_author(self, author: str) -> "HeadlineFilter":
        if not author:
            return self
        author_lower = author.lower()
        self._data = [h for h in self._data if author_lower in str(h.get("author", "")).lower()]
        return self

    def bookmarked_only(self) -> "HeadlineFilter":
        self._data = [h for h in self._data if h.get("bookmarked")]
        return self

    def favourites_only(self) -> "HeadlineFilter":
        self._data = [h for h in self._data if h.get("favourite")]
        return self

    def by_date_range(self, start: Optional[str] = None, end: Optional[str] = None,
                      date_field: str = "scraped_time") -> "HeadlineFilter":
        def _in_range(row: HeadlineRow) -> bool:
            raw = str(row.get(date_field, "") or "")
            if not raw:
                return False
            date_part = raw[:10]
            if start and date_part < start:
                return False
            if end and date_part > end:
                return False
            return True

        if start or end:
            self._data = [h for h in self._data if _in_range(h)]
        return self

    def sort_by(self, column: str = "scraped_time", ascending: bool = False) -> "HeadlineFilter":
        try:
            self._data.sort(key=lambda h: str(h.get(column, "") or "").lower(), reverse=not ascending)
        except Exception as exc:
            log.warning("Sort by '%s' failed: %s", column, exc)
        return self

    def sort_alphabetically(self, ascending: bool = True) -> "HeadlineFilter":
        return self.sort_by("title", ascending=ascending)

    def sort_by_latest(self) -> "HeadlineFilter":
        return self.sort_by("scraped_time", ascending=False)

    def sort_by_oldest(self) -> "HeadlineFilter":
        return self.sort_by("scraped_time", ascending=True)

    def deduplicate(self, key: str = "url") -> "HeadlineFilter":
        seen: set = set()
        unique: List[HeadlineRow] = []
        for h in self._data:
            val = h.get(key, "")
            if val not in seen:
                seen.add(val)
                unique.append(h)
        self._data = unique
        return self

    def paginate(self, page: int = 1, page_size: int = 50) -> "HeadlineFilter":
        start = (max(page, 1) - 1) * page_size
        self._data = self._data[start: start + page_size]
        return self

    def results(self) -> List[HeadlineRow]:
        return self._data

    @property
    def count(self) -> int:
        return len(self._data)

    def top_keywords(self, n: int = 20, min_length: int = 4) -> List[tuple]:
        stop_words = {
            "the", "and", "for", "are", "but", "not", "you", "all",
            "can", "had", "her", "was", "one", "our", "out", "has",
            "have", "that", "this", "with", "will", "from", "they",
            "been", "said", "each", "which", "their", "what", "about",
            "would", "there", "when", "make", "like", "than", "them",
            "some", "could", "into", "after", "more", "also", "over",
            "such", "most", "says", "just", "very", "year", "much",
        }
        words: List[str] = []
        for h in self._data:
            title = str(h.get("title", ""))
            tokens = re.findall(r"[a-zA-Z]+", title.lower())
            words.extend(t for t in tokens if len(t) >= min_length and t not in stop_words)
        return Counter(words).most_common(n)

    def __repr__(self) -> str:
        return f"<HeadlineFilter rows={self.count}>"
