from __future__ import annotations

import random
import time
import urllib.robotparser
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any, Callable, Dict, List, Optional
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup

from logger import get_logger
from settings import Settings
from utils import default_headers, normalise_url, sanitise_text, parse_timestamp, now_iso

log = get_logger(__name__)

HeadlineDict = Dict[str, Any]
ProgressCallback = Optional[Callable[[float, str], None]]

_robots_cache: Dict[str, urllib.robotparser.RobotFileParser] = {}


def _can_fetch(url: str, user_agent: str = "*") -> bool:
    parsed = urlparse(url)
    robots_url = f"{parsed.scheme}://{parsed.netloc}/robots.txt"
    if robots_url not in _robots_cache:
        rp = urllib.robotparser.RobotFileParser()
        rp.set_url(robots_url)
        try:
            rp.read()
        except Exception:
            return True
        _robots_cache[robots_url] = rp
    return _robots_cache[robots_url].can_fetch(user_agent, url)


class _SourceScraper:
    def __init__(self, source_config: Dict[str, Any], settings: Settings) -> None:
        self.name: str = source_config["name"]
        self.base_url: str = source_config["base_url"]
        self.category: str = source_config.get("category", "General")
        self.selectors: Dict[str, str] = source_config.get("selectors", {})
        self._cfg = settings

    def scrape(self) -> List[HeadlineDict]:
        if self._cfg.respect_robots_txt and not _can_fetch(self.base_url):
            log.warning("[%s] Blocked by robots.txt -- skipping.", self.name)
            return []
        html = self._fetch_with_retry()
        if not html:
            return []
        return self._parse(html)

    def _fetch_with_retry(self) -> Optional[str]:
        retries = self._cfg.retry_count
        timeout = self._cfg.request_timeout
        delay = self._cfg.request_delay

        for attempt in range(1, retries + 1):
            try:
                headers = default_headers()
                resp = requests.get(self.base_url, headers=headers, timeout=timeout, allow_redirects=True)
                resp.raise_for_status()
                log.info("[%s] Fetched OK (%d bytes, %d ms)", self.name, len(resp.content),
                         int(resp.elapsed.total_seconds() * 1000))
                return resp.text
            except requests.exceptions.HTTPError as exc:
                status = exc.response.status_code if exc.response is not None else "?"
                log.warning("[%s] HTTP %s on attempt %d", self.name, status, attempt)
            except requests.exceptions.ConnectionError:
                log.warning("[%s] Connection error on attempt %d", self.name, attempt)
            except requests.exceptions.Timeout:
                log.warning("[%s] Timeout on attempt %d", self.name, attempt)
            except requests.exceptions.RequestException as exc:
                log.error("[%s] Request error: %s", self.name, exc)
                return None

            if attempt < retries:
                wait = delay * (2 ** (attempt - 1)) + random.uniform(0, 1)
                time.sleep(wait)

        log.error("[%s] All %d attempts exhausted.", self.name, retries)
        return None

    def _parse(self, html: str) -> List[HeadlineDict]:
        soup = BeautifulSoup(html, "lxml")
        article_sel = self.selectors.get("article", "article")
        articles = soup.select(article_sel)

        if not articles:
            log.warning("[%s] No articles found with selector '%s'.", self.name, article_sel)
            return []

        headlines: List[HeadlineDict] = []
        scraped_at = now_iso()
        for article in articles:
            headline = self._parse_article(article, scraped_at)
            if headline:
                headlines.append(headline)

        log.info("[%s] Parsed %d headlines from %d article blocks.", self.name, len(headlines), len(articles))
        return headlines

    def _parse_article(self, article: Any, scraped_at: str) -> Optional[HeadlineDict]:
        title_sel = self.selectors.get("title", "h2, h3")
        title_el = article.select_one(title_sel)
        title = sanitise_text(title_el.get_text() if title_el else "")
        if not title:
            return None

        link_sel = self.selectors.get("link", "a")
        link_attr = self.selectors.get("link_attr", "href")
        link_el = article.select_one(link_sel)
        raw_url = ""
        if link_el:
            raw_url = link_el.get(link_attr, "") or ""
        if not raw_url and title_el:
            parent_a = title_el.find_parent("a")
            if parent_a:
                raw_url = parent_a.get("href", "") or ""

        url = normalise_url(raw_url, self.base_url)
        if not url or len(url) < 10:
            return None

        author_sel = self.selectors.get("author", "")
        author = ""
        if author_sel:
            author_el = article.select_one(author_sel)
            author = sanitise_text(author_el.get_text() if author_el else "")

        cat_sel = self.selectors.get("category", "")
        category = self.category
        if cat_sel:
            cat_el = article.select_one(cat_sel)
            parsed_cat = sanitise_text(cat_el.get_text() if cat_el else "")
            if parsed_cat:
                category = parsed_cat

        time_sel = self.selectors.get("time", "time")
        pub_time = None
        if time_sel:
            time_el = article.select_one(time_sel)
            if time_el:
                raw_time = time_el.get("datetime") or time_el.get_text()
                pub_time = parse_timestamp(raw_time)

        return {
            "title": title, "source": self.name, "author": author,
            "category": category, "published_time": pub_time or "",
            "url": url, "scraped_time": scraped_at,
        }


class ScraperEngine:
    def __init__(self) -> None:
        self._cfg = Settings()
        self._sources = self._cfg.news_sources
        self._stop_flag: bool = False

    @property
    def available_sources(self) -> List[Dict[str, Any]]:
        return list(self._sources)

    @property
    def enabled_sources(self) -> List[Dict[str, Any]]:
        return [s for s in self._sources if s.get("enabled", True)]

    def get_source_names(self) -> List[str]:
        return [s["name"] for s in self._sources]

    def request_stop(self) -> None:
        self._stop_flag = True
        log.info("Stop requested.")

    def reset_stop(self) -> None:
        self._stop_flag = False

    def scrape_all(self, on_progress: ProgressCallback = None) -> List[HeadlineDict]:
        return self._scrape_sources(self.enabled_sources, on_progress)

    def scrape_selected(self, source_names: List[str], on_progress: ProgressCallback = None) -> List[HeadlineDict]:
        name_set = set(source_names)
        sources = [s for s in self._sources if s["name"] in name_set]
        if not sources:
            log.warning("No matching sources for: %s", source_names)
            return []
        return self._scrape_sources(sources, on_progress)

    def _scrape_sources(self, sources: List[Dict[str, Any]], on_progress: ProgressCallback) -> List[HeadlineDict]:
        self.reset_stop()
        all_headlines: List[HeadlineDict] = []
        total = len(sources)
        if total == 0:
            return []

        log.info("Starting scrape of %d source(s) ...", total)
        completed = 0
        max_workers = min(self._cfg.max_threads, total)

        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            future_to_name = {executor.submit(self._scrape_one, src): src["name"] for src in sources}
            for future in as_completed(future_to_name):
                if self._stop_flag:
                    log.info("Stop flag set -- cancelling remaining sources.")
                    executor.shutdown(wait=False, cancel_futures=True)
                    break
                name = future_to_name[future]
                try:
                    results = future.result()
                    all_headlines.extend(results)
                    log.info("[%s] Collected %d headlines.", name, len(results))
                except Exception as exc:
                    log.error("[%s] Scraper crashed: %s", name, exc)
                completed += 1
                if on_progress:
                    on_progress(completed / total * 100, f"Scraped {name} ({completed}/{total})")

        log.info("Scrape complete: %d headlines from %d/%d sources.", len(all_headlines), completed, total)
        return all_headlines

    def _scrape_one(self, source_config: Dict[str, Any]) -> List[HeadlineDict]:
        scraper = _SourceScraper(source_config, self._cfg)
        results = scraper.scrape()
        delay = self._cfg.request_delay
        if delay > 0:
            time.sleep(delay)
        return results
