"""Quick smoke test for the HeadlineFilter class."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from filters import HeadlineFilter
from logger import setup_logging

setup_logging()

data = [
    {"title": "Market Rally Today", "source": "Reuters", "url": "http://a.com",
     "category": "Business", "scraped_time": "2025-07-11", "author": "Jane"},
    {"title": "Climate Change Report", "source": "BBC News", "url": "http://b.com",
     "category": "World", "scraped_time": "2025-07-10", "author": "Tom"},
    {"title": "Market Crash Fears", "source": "CNN", "url": "http://c.com",
     "category": "Business", "scraped_time": "2025-07-09", "author": "Sarah"},
    {"title": "Market Rally Today", "source": "NDTV", "url": "http://a.com",
     "category": "Business", "scraped_time": "2025-07-11", "author": "Duplicate"},
]

# Keyword + sort
r = HeadlineFilter(data).keyword("market").sort_alphabetically().results()
print(f"1. Keyword 'market' + sort A-Z: {len(r)} results")
for x in r:
    print(f"   - {x['title']}")
assert len(r) == 3

# Source filter
r2 = HeadlineFilter(data).by_source("Reuters").results()
print(f"\n2. Source 'Reuters': {len(r2)} results")
assert len(r2) == 1

# Category filter
r3 = HeadlineFilter(data).by_category("Business").results()
print(f"\n3. Category 'Business': {len(r3)} results")
assert len(r3) == 3

# Deduplicate by URL
r4 = HeadlineFilter(data).deduplicate("url").results()
print(f"\n4. Deduplicate by URL: {len(r4)} (from {len(data)})")
assert len(r4) == 3

# Pagination
r5 = HeadlineFilter(data).paginate(page=1, page_size=2).results()
print(f"\n5. Page 1, size 2: {len(r5)} results")
assert len(r5) == 2

# Top keywords
kw = HeadlineFilter(data).top_keywords(5, 3)
print(f"\n6. Top keywords: {kw}")
assert any(w == "market" for w, _ in kw)

# Chained
r6 = (
    HeadlineFilter(data)
    .keyword("market")
    .by_category("Business")
    .sort_by_latest()
    .deduplicate()
    .results()
)
print(f"\n7. Chained (market + Business + latest + dedup): {len(r6)} results")

print("\n[ALL FILTER TESTS PASSED]")
