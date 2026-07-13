"""
NewsScrape Pro — Full Integration Test Suite
=============================================

Tests every module's public API in isolation and in combination.
Run:  python tests/test_integration.py
"""

from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from matplotlib.figure import Figure

from logger import setup_logging, get_logger
from settings import Settings
from database import DatabaseManager
from filters import HeadlineFilter
from exporter import DataExporter
from analytics import AnalyticsEngine
from scraper import ScraperEngine
from scheduler import ScrapeScheduler
from utils import (
    sanitise_text, slugify, truncate, normalise_url,
    is_valid_url, now_iso, now_display, parse_timestamp,
    human_readable_size, safe_filename, random_user_agent,
    default_headers,
)

log_root = setup_logging()
log = get_logger(__name__)

PASS = 0
FAIL = 0


def _test(name: str, condition: bool) -> None:
    global PASS, FAIL
    status = "PASS" if condition else "FAIL"
    symbol = "[OK]" if condition else "[!!]"
    print(f"  {symbol} {name}")
    if condition:
        PASS += 1
    else:
        FAIL += 1


def _section(title: str) -> None:
    print(f"\n{'='*60}")
    print(f"  {title}")
    print(f"{'='*60}")


def test_utils():
    _section("UTILS")
    _test("sanitise_text strips whitespace", sanitise_text("  hello   world  ") == "hello world")
    _test("sanitise_text handles None", sanitise_text(None) == "")
    _test("slugify works", slugify("Hello World!") == "hello-world")
    _test("truncate with short text", truncate("Hi", 10) == "Hi")
    _test("normalise_url resolves relative", "bbc.com" in normalise_url("/news", "https://www.bbc.com"))
    _test("is_valid_url accepts https", is_valid_url("https://example.com"))
    _test("is_valid_url rejects empty", not is_valid_url(""))
    _test("now_iso returns Z suffix", now_iso().endswith("Z"))
    _test("now_display returns non-empty", len(now_display()) > 5)
    _test("parse_timestamp ISO", parse_timestamp("2025-07-11T08:30:00Z") is not None)
    _test("parse_timestamp returns None for garbage", parse_timestamp("not a date") is None)
    _test("human_readable_size", "1.00 MB" == human_readable_size(1_048_576))
    _test("safe_filename strips bad chars", "/" not in safe_filename("a/b:c"))
    _test("random_user_agent is string", len(random_user_agent()) > 10)
    _test("default_headers has UA", "User-Agent" in default_headers())


def test_settings():
    _section("SETTINGS")
    cfg = Settings()
    _test("app_name is set", cfg.app_name == "NewsScrape Pro")
    _test("app_version is set", cfg.app_version == "1.0.0")
    _test("window_width is int", isinstance(cfg.window_width, int))
    _test("request_timeout is int", isinstance(cfg.request_timeout, int))
    _test("database_path is Path", isinstance(cfg.database_path, Path))
    _test("log_file is Path", isinstance(cfg.log_file, Path))
    _test("news_sources is list", isinstance(cfg.news_sources, list))
    _test("news_sources has items", len(cfg.news_sources) >= 1)
    _test("theme is string", cfg.theme in ("dark", "light", "system"))


def test_database():
    _section("DATABASE")
    test_path = PROJECT_ROOT / "database" / "test_integration.db"
    if test_path.exists():
        test_path.unlink()

    db = DatabaseManager(db_path=test_path)

    data = [
        {"title": "Test Headline 1", "source": "TestSource", "url": "http://test.com/1",
         "category": "Tech", "author": "Tester", "published_time": "", "scraped_time": now_iso()},
        {"title": "Test Headline 2", "source": "TestSource", "url": "http://test.com/2",
         "category": "Science", "author": "", "published_time": "", "scraped_time": now_iso()},
    ]

    inserted, skipped = db.insert_many(data)
    _test("bulk insert works", inserted == 2)
    _test("no duplicates on first insert", skipped == 0)

    i2, s2 = db.insert_many(data)
    _test("duplicates are skipped", i2 == 0 and s2 == 2)

    all_h = db.get_all_headlines()
    _test("get_all returns correct count", len(all_h) == 2)

    results = db.search("headline")
    _test("search finds matches", len(results) == 2)

    stats = db.get_statistics()
    _test("statistics returns dict", isinstance(stats, dict))
    _test("total_headlines is 2", stats.get("total_headlines") == 2)

    db.toggle_bookmark(all_h[0]["id"])
    bm = db.get_bookmarked()
    _test("bookmark works", len(bm) == 1)

    db.log_activity("test_action", "test details")
    activity = db.get_recent_activity()
    _test("activity log works", len(activity) >= 1)

    db.save_search("test query")
    searches = db.get_recent_searches()
    _test("search history works", len(searches) >= 1)

    backup = db.backup()
    _test("backup creates file", backup is not None and backup.exists())

    # Cleanup
    if test_path.exists():
        test_path.unlink()
    if backup and backup.exists():
        backup.unlink()


def test_filters():
    _section("FILTERS")
    data = [
        {"title": "Alpha News", "source": "A", "url": "http://a.com", "category": "Tech",
         "scraped_time": "2025-07-11"},
        {"title": "Beta News", "source": "B", "url": "http://b.com", "category": "Science",
         "scraped_time": "2025-07-10"},
        {"title": "Alpha Update", "source": "A", "url": "http://c.com", "category": "Tech",
         "scraped_time": "2025-07-09"},
    ]

    f = HeadlineFilter(data)
    _test("filter init", f.count == 3)

    r = HeadlineFilter(data).keyword("alpha").results()
    _test("keyword filter", len(r) == 2)

    r = HeadlineFilter(data).by_source("A").results()
    _test("source filter", len(r) == 2)

    r = HeadlineFilter(data).by_category("Science").results()
    _test("category filter", len(r) == 1)

    r = HeadlineFilter(data).sort_alphabetically().results()
    _test("sort alphabetical", r[0]["title"] == "Alpha News")

    r = HeadlineFilter(data).sort_by_latest().results()
    _test("sort latest first", r[0]["scraped_time"] == "2025-07-11")

    kw = HeadlineFilter(data).top_keywords(5, 3)
    _test("top_keywords returns list", isinstance(kw, list))


def test_exporter():
    _section("EXPORTER")
    exp_dir = PROJECT_ROOT / "exports" / "test_export"
    exp = DataExporter(export_dir=exp_dir)

    data = [
        {"title": "Export Test", "source": "Test", "author": "A", "category": "X",
         "published_time": "", "url": "http://test.com", "scraped_time": now_iso(), "id": 1},
    ]

    csv_path = exp.to_csv(data, "test.csv")
    _test("CSV export creates file", csv_path.exists())

    json_path = exp.to_json(data, "test.json")
    _test("JSON export creates file", json_path.exists())

    xlsx_path = exp.to_excel(data, "test.xlsx")
    _test("Excel export creates file", xlsx_path.exists())

    # Cleanup
    import shutil
    if exp_dir.exists():
        shutil.rmtree(exp_dir)


def test_analytics():
    _section("ANALYTICS")
    engine = AnalyticsEngine(dark_mode=True)

    src_data = [{"source": "A", "count": 10}, {"source": "B", "count": 5}]
    fig = engine.headlines_per_source(src_data)
    _test("headlines_per_source returns Figure", isinstance(fig, Figure))

    cat_data = [{"category": "Tech", "count": 8}, {"category": "Science", "count": 4}]
    fig = engine.category_distribution(cat_data)
    _test("category_distribution returns Figure", isinstance(fig, Figure))

    kw_data = [("python", 10), ("news", 7), ("data", 5)]
    fig = engine.top_keywords(kw_data)
    _test("top_keywords returns Figure", isinstance(fig, Figure))

    daily = [{"date": "2025-07-10", "count": 5}, {"date": "2025-07-11", "count": 8}]
    fig = engine.daily_activity(daily)
    _test("daily_activity returns Figure", isinstance(fig, Figure))

    fig = engine.weekly_trend(daily)
    _test("weekly_trend returns Figure", isinstance(fig, Figure))

    # Empty data
    fig = engine.daily_activity([])
    _test("daily_activity handles empty data", isinstance(fig, Figure))


def test_scraper():
    _section("SCRAPER")
    engine = ScraperEngine()
    _test("available_sources is list", isinstance(engine.available_sources, list))
    _test("has sources configured", len(engine.available_sources) >= 1)
    _test("enabled_sources is list", isinstance(engine.enabled_sources, list))
    _test("get_source_names returns names", all(isinstance(n, str) for n in engine.get_source_names()))
    _test("stop/reset flags work", (engine.request_stop(), engine.reset_stop(), True)[-1])


def test_scheduler():
    _section("SCHEDULER")
    called = []
    sched = ScrapeScheduler(
        scrape_fn=lambda: called.append(1),
        on_tick=lambda msg: None,
    )
    _test("scheduler not running initially", not sched.is_running)
    sched.start(interval_minutes=60)
    _test("scheduler starts", sched.is_running)
    _test("interval is correct", sched.interval_minutes == 60)
    sched.stop()
    import time
    time.sleep(0.5)
    _test("scheduler stops", not sched.is_running)


def main():
    print("\n" + "=" * 60)
    print("  NewsScrape Pro — Full Integration Test Suite")
    print("=" * 60)

    test_utils()
    test_settings()
    test_database()
    test_filters()
    test_exporter()
    test_analytics()
    test_scraper()
    test_scheduler()

    print(f"\n{'='*60}")
    print(f"  RESULTS: {PASS} passed, {FAIL} failed")
    print(f"{'='*60}\n")

    if FAIL > 0:
        sys.exit(1)


if __name__ == "__main__":
    main()
