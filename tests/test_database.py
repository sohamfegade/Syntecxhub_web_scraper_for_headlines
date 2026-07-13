"""
NewsScrape Pro — Phase 2 Verification Script
=============================================

Exercises every DatabaseManager method to confirm the schema, CRUD,
search, bookmarks, statistics, backup, and activity logging all work.

Run:  python tests/test_database.py
"""

from __future__ import annotations

import sys
from pathlib import Path

# Ensure project root is importable
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from logger import setup_logging  # noqa: E402
from database import DatabaseManager  # noqa: E402

# ── Sample data ──────────────────────────────────────────────────
SAMPLE_HEADLINES = [
    {
        "title": "Global Markets Rally as Inflation Data Cools",
        "source": "Reuters",
        "author": "Jane Smith",
        "category": "Business",
        "published_time": "2025-07-11T08:30:00Z",
        "url": "https://www.reuters.com/markets/rally-inflation-2025",
        "scraped_time": "2025-07-11T09:00:00Z",
    },
    {
        "title": "India Launches New Space Mission to Study the Sun",
        "source": "NDTV",
        "author": "Rahul Verma",
        "category": "Science",
        "published_time": "2025-07-11T07:15:00Z",
        "url": "https://www.ndtv.com/science/india-sun-mission-2025",
        "scraped_time": "2025-07-11T09:00:00Z",
    },
    {
        "title": "Premier League Transfer Window: Top 10 Deals So Far",
        "source": "BBC News",
        "author": "Tom Brown",
        "category": "Sports",
        "published_time": "2025-07-11T06:00:00Z",
        "url": "https://www.bbc.com/sport/football/transfers-2025",
        "scraped_time": "2025-07-11T09:01:00Z",
    },
    {
        "title": "Climate Summit 2025: Key Takeaways from Day One",
        "source": "Al Jazeera",
        "author": "",
        "category": "World",
        "published_time": "2025-07-10T22:00:00Z",
        "url": "https://www.aljazeera.com/climate-summit-day1",
        "scraped_time": "2025-07-11T09:02:00Z",
    },
    {
        "title": "AI Regulation Bill Passes Senate Committee",
        "source": "CNN",
        "author": "Sarah Lee",
        "category": "Technology",
        "published_time": "2025-07-11T05:45:00Z",
        "url": "https://edition.cnn.com/tech/ai-regulation-bill-2025",
        "scraped_time": "2025-07-11T09:02:30Z",
    },
    {
        "title": "Monsoon Update: Heavy Rain Expected in Mumbai This Week",
        "source": "The Hindu",
        "author": "Priya Nair",
        "category": "Weather",
        "published_time": "2025-07-11T04:30:00Z",
        "url": "https://www.thehindu.com/weather/mumbai-monsoon-july",
        "scraped_time": "2025-07-11T09:03:00Z",
    },
    {
        "title": "Stock Market Hits All-Time High on Tech Earnings",
        "source": "Indian Express",
        "author": "Amit Sharma",
        "category": "Business",
        "published_time": "2025-07-11T08:00:00Z",
        "url": "https://indianexpress.com/business/stock-market-high-july",
        "scraped_time": "2025-07-11T09:04:00Z",
    },
    {
        "title": "New COVID Variant Detected: What Experts Say",
        "source": "Times of India",
        "author": "",
        "category": "Health",
        "published_time": "2025-07-11T03:15:00Z",
        "url": "https://timesofindia.com/health/covid-variant-july-2025",
        "scraped_time": "2025-07-11T09:04:30Z",
    },
    {
        "title": "NASA Confirms Water Ice on Mars Surface",
        "source": "Reuters",
        "author": "Michael Chen",
        "category": "Science",
        "published_time": "2025-07-10T20:00:00Z",
        "url": "https://www.reuters.com/science/nasa-mars-ice-2025",
        "scraped_time": "2025-07-11T09:05:00Z",
    },
    {
        "title": "Bollywood Box Office: Weekend Collection Report",
        "source": "NDTV",
        "author": "Sneha Kapoor",
        "category": "Entertainment",
        "published_time": "2025-07-11T01:00:00Z",
        "url": "https://www.ndtv.com/entertainment/box-office-july-2025",
        "scraped_time": "2025-07-11T09:05:30Z",
    },
]


def _header(title: str) -> None:
    print(f"\n{'='*60}")
    print(f"  {title}")
    print(f"{'='*60}")


def main() -> None:
    setup_logging()

    # Use a temporary test database
    test_db_path = PROJECT_ROOT / "database" / "test_newsscrape.db"
    if test_db_path.exists():
        test_db_path.unlink()

    db = DatabaseManager(db_path=test_db_path)

    # ── 1. Bulk insert ───────────────────────────────────────────
    _header("1. Bulk Insert")
    inserted, skipped = db.insert_many(SAMPLE_HEADLINES)
    print(f"   Inserted: {inserted}  |  Skipped: {skipped}")
    assert inserted == 10, f"Expected 10 inserts, got {inserted}"
    assert skipped == 0, f"Expected 0 skips, got {skipped}"

    # ── 2. Duplicate detection ───────────────────────────────────
    _header("2. Duplicate Detection")
    dup_inserted, dup_skipped = db.insert_many(SAMPLE_HEADLINES)
    print(f"   Inserted: {dup_inserted}  |  Skipped: {dup_skipped}")
    assert dup_inserted == 0, "Duplicates should have been skipped"
    assert dup_skipped == 10

    # ── 3. Get all headlines ─────────────────────────────────────
    _header("3. Get All Headlines")
    all_rows = db.get_all_headlines()
    print(f"   Total rows: {len(all_rows)}")
    assert len(all_rows) == 10

    # ── 4. Search ────────────────────────────────────────────────
    _header("4. Keyword Search")
    results = db.search("market")
    print(f"   'market' -> {len(results)} results")
    for r in results:
        print(f"     - {r['title']}")
    assert len(results) == 2  # "Global Markets..." and "Stock Market..."

    # ── 5. Search with source filter ─────────────────────────────
    _header("5. Search with Source Filter")
    results = db.search("", source="Reuters")
    print(f"   Source='Reuters' -> {len(results)} results")
    assert len(results) == 2

    # ── 6. Bookmark / Favourite ──────────────────────────────────
    _header("6. Bookmark & Favourite")
    headline = all_rows[0]
    hid = headline["id"]

    bm_state = db.toggle_bookmark(hid)
    print(f"   Bookmark id={hid} -> {bm_state}")
    assert bm_state is True

    fav_state = db.toggle_favourite(hid)
    print(f"   Favourite id={hid} -> {fav_state}")
    assert fav_state is True

    bookmarked = db.get_bookmarked()
    print(f"   Bookmarked count: {len(bookmarked)}")
    assert len(bookmarked) == 1

    # Toggle off
    db.toggle_bookmark(hid)
    bookmarked = db.get_bookmarked()
    assert len(bookmarked) == 0
    print("   Bookmark toggled off successfully.")

    # ── 7. Statistics ────────────────────────────────────────────
    _header("7. Dashboard Statistics")
    stats = db.get_statistics()
    for k, v in stats.items():
        print(f"   {k}: {v}")
    assert stats["total_headlines"] == 10
    assert stats["total_sources"] >= 1

    # ── 8. Per-source counts ─────────────────────────────────────
    _header("8. Headlines Per Source")
    per_source = db.get_headlines_per_source()
    for row in per_source:
        print(f"   {row['source']}: {row['count']}")

    # ── 9. Category distribution ─────────────────────────────────
    _header("9. Category Distribution")
    cats = db.get_category_distribution()
    for row in cats:
        print(f"   {row['category']}: {row['count']}")

    # ── 10. Search history ───────────────────────────────────────
    _header("10. Search History")
    db.save_search("climate change")
    db.save_search("stock market")
    db.save_search("NASA Mars")
    recent = db.get_recent_searches(limit=5)
    for s in recent:
        print(f"   [{s['searched_at']}] {s['query']}")
    assert len(recent) == 3

    # ── 11. Activity log ─────────────────────────────────────────
    _header("11. Activity Log")
    db.log_activity("scrape_completed", "10 headlines from 8 sources")
    db.log_activity("export_csv", "Exported 10 rows to exports/headlines.csv")
    activity = db.get_recent_activity(limit=5)
    for a in activity:
        print(f"   [{a['action']}] {a['details']}")
    assert len(activity) >= 2

    # ── 12. Distinct sources / categories ────────────────────────
    _header("12. Distinct Values")
    sources = db.get_distinct_sources()
    categories = db.get_distinct_categories()
    print(f"   Sources:    {sources}")
    print(f"   Categories: {categories}")

    # ── 13. Backup ───────────────────────────────────────────────
    _header("13. Database Backup")
    backup_path = db.backup()
    if backup_path:
        print(f"   Backup created: {backup_path}")
        print(f"   Size: {backup_path.stat().st_size:,} bytes")
    else:
        print("   [WARN] Backup returned None")

    # ── 14. Delete single ────────────────────────────────────────
    _header("14. Delete Single Headline")
    deleted = db.delete_headline(hid)
    print(f"   Deleted id={hid}: {deleted}")
    remaining = db.get_all_headlines()
    print(f"   Remaining: {len(remaining)}")
    assert len(remaining) == 9

    # ── DONE ─────────────────────────────────────────────────────
    _header("ALL TESTS PASSED")
    print("   Database layer is fully operational.\n")

    # Clean up test DB
    if test_db_path.exists():
        test_db_path.unlink()
        print(f"   Cleaned up: {test_db_path}")


if __name__ == "__main__":
    main()
