<p align="center">
  <img src="assets/icons/app_icon.png" alt="NewsScrape Pro" width="120" />
</p>

<h1 align="center">NewsScrape Pro</h1>
<h3 align="center">Advanced Multi-Source News Headline Scraper</h3>

<p align="center">
  <img src="https://img.shields.io/badge/python-3.11%2B-blue?style=for-the-badge&logo=python&logoColor=white" />
  <img src="https://img.shields.io/badge/GUI-CustomTkinter-green?style=for-the-badge" />
  <img src="https://img.shields.io/badge/database-SQLite-orange?style=for-the-badge&logo=sqlite&logoColor=white" />
  <img src="https://img.shields.io/badge/license-MIT-purple?style=for-the-badge" />
</p>

<p align="center">
  A professional desktop application that automatically scrapes the latest headlines from <strong>8+ trusted global news sources</strong>, stores them in a local database, and lets you search, filter, visualise, and export the data — all through a modern dark-themed GUI.
</p>

---

## ✨ Features

| Category | Highlights |
|---|---|
| **Scraping** | Multi-source, threaded scraping with retry logic, random User-Agent rotation, request delays, and robots.txt awareness |
| **GUI** | Premium CustomTkinter interface with dark/light themes, sidebar navigation, animated cards, progress bars, and status bar |
| **Database** | SQLite storage with duplicate detection, bookmarking, favourites, and automatic backup |
| **Search & Filter** | Keyword search, source/category filters, alphabetical/chronological sorting, duplicate removal |
| **Analytics** | Matplotlib charts — headlines per source, category distribution, keyword cloud, daily & weekly trends |
| **Export** | One-click export to CSV, JSON, and Excel with timestamped filenames |
| **Automation** | Background scheduler with configurable intervals (15 min / 30 min / 1 hr / custom) |
| **Logging** | Rotating file logs with configurable size limits and backup count |
| **Security** | Respectful scraping — honours robots.txt, randomised delays, realistic headers |

---

## 📸 Screenshots

> Screenshots will be added after Phase 4 (GUI implementation).

| Dashboard | Scraper | Analytics |
|---|---|---|
| *coming soon* | *coming soon* | *coming soon* |

---

## 🏗️ Architecture

```
NewsScrape Pro follows a layered MVC-inspired architecture:

┌──────────────────────────────────────────────┐
│                  main.py                     │  ← Entry point
├──────────────────────────────────────────────┤
│                  gui.py                      │  ← View (CustomTkinter)
├──────────────┬───────────────┬───────────────┤
│  scraper.py  │  database.py  │  analytics.py │  ← Controllers / Services
├──────────────┼───────────────┼───────────────┤
│  filters.py  │  exporter.py  │  scheduler.py │  ← Supporting services
├──────────────┴───────────────┴───────────────┤
│    settings.py  │  logger.py  │  utils.py    │  ← Infrastructure
└──────────────────────────────────────────────┘
```

---

## 📂 Folder Structure

```
NewsScrapePro/
│
├── main.py                 # Application entry point
├── gui.py                  # CustomTkinter GUI (View layer)
├── scraper.py              # Web scraping engine
├── database.py             # SQLite data access layer
├── analytics.py            # Matplotlib chart generation
├── scheduler.py            # Background task scheduler
├── filters.py              # Search & filter logic
├── exporter.py             # CSV / JSON / Excel export
├── logger.py               # Rotating-file logging setup
├── settings.py             # Configuration singleton
├── utils.py                # Shared utility functions
│
├── requirements.txt        # Python dependencies
├── README.md               # This file
├── .gitignore              # Git ignore rules
├── .env.example            # Environment variable template
│
├── config/
│   ├── default_settings.ini    # Factory-default configuration
│   ├── user_settings.ini       # User overrides (git-ignored)
│   └── sources.json            # News source registry & CSS selectors
│
├── database/
│   └── newsscrape.db           # SQLite database (git-ignored)
│
├── exports/                    # Exported CSV / JSON / Excel files
│
├── logs/
│   └── scraper.log             # Application log (git-ignored)
│
└── assets/
    ├── icons/                  # Application & UI icons
    └── themes/                 # Custom theme files
```

---

## 📰 Supported News Sources

| # | Source | Region | Default |
|---|--------|--------|---------|
| 1 | BBC News | Global | ✅ |
| 2 | Reuters | Global | ✅ |
| 3 | CNN | Global | ✅ |
| 4 | NDTV | India | ✅ |
| 5 | The Hindu | India | ✅ |
| 6 | Indian Express | India | ✅ |
| 7 | Times of India | India | ✅ |
| 8 | Al Jazeera | Global | ✅ |

> Additional sources can be added by editing `config/sources.json` — no code changes required.

---

## 🚀 Installation

### Prerequisites

- **Python 3.11** or higher
- **pip** (comes with Python)
- **Git** (optional, for cloning)

### Steps

```bash
# 1. Clone the repository
git clone https://github.com/yourusername/NewsScrape-Pro.git
cd NewsScrape-Pro

# 2. Create a virtual environment (recommended)
python -m venv venv

# Windows
venv\Scripts\activate

# macOS / Linux
source venv/bin/activate

# 3. Install dependencies
pip install -r requirements.txt

# 4. (Optional) Copy and configure environment variables
copy .env.example .env        # Windows
cp .env.example .env          # macOS / Linux

# 5. Run the application
python main.py
```

### Command-Line Options

```bash
python main.py              # Normal launch
python main.py --reset      # Reset all settings to factory defaults
```

---

## 🗄️ Database Schema

```sql
CREATE TABLE IF NOT EXISTS headlines (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    title           TEXT    NOT NULL,
    source          TEXT    NOT NULL,
    author          TEXT    DEFAULT '',
    category        TEXT    DEFAULT 'General',
    published_time  TEXT,
    url             TEXT    NOT NULL UNIQUE,
    scraped_time    TEXT    NOT NULL,
    bookmarked      INTEGER DEFAULT 0,
    favourite       INTEGER DEFAULT 0
);
```

---

## 📊 Data Extracted

Each scraped headline captures:

| Field | Description |
|-------|-------------|
| `title` | Headline text |
| `source` | News website name |
| `author` | Journalist name (if available) |
| `category` | News category (World, India, Tech, etc.) |
| `published_time` | When the article was published |
| `url` | Direct link to the article |
| `scraped_time` | When NewsScrape Pro collected the data |

---

## ⚙️ Configuration

All settings are managed through INI files in the `config/` directory:

| File | Purpose |
|------|---------|
| `default_settings.ini` | Factory defaults — **do not edit** |
| `user_settings.ini` | Your personal overrides (auto-created) |

Key settings:

```ini
[scraper]
request_timeout = 15
retry_count = 3
request_delay = 2.0
random_user_agent = true
respect_robots_txt = true

[scheduler]
enabled = false
interval_minutes = 60

[export]
auto_export = false
default_format = csv
```

---

## 🔮 Future Improvements

- [ ] RSS feed support alongside HTML scraping
- [ ] Sentiment analysis on headlines (NLP)
- [ ] Headline deduplication via fuzzy string matching
- [ ] Email / desktop notifications for breaking news keywords
- [ ] REST API mode (Flask/FastAPI) for headless operation
- [ ] Docker containerisation
- [ ] Cloud database sync (PostgreSQL / Firebase)
- [ ] Multi-language headline support
- [ ] Browser extension companion

---

## 🛡️ Ethics & Compliance

NewsScrape Pro is designed for **educational and personal research** use:

- Respects `robots.txt` directives by default.
- Applies randomised delays between requests to avoid server strain.
- Rotates User-Agent strings to behave like a standard browser.
- Does **not** bypass paywalls or CAPTCHAs.
- Users are responsible for complying with each website's Terms of Service.

---

## 📝 License

This project is licensed under the **MIT License** — see the [LICENSE](LICENSE) file for details.

---

## 🙏 Credits

| Component | Credit |
|-----------|--------|
| GUI Framework | [CustomTkinter](https://github.com/TomSchimansky/CustomTkinter) by Tom Schimansky |
| Web Scraping | [BeautifulSoup4](https://www.crummy.com/software/BeautifulSoup/) & [Requests](https://requests.readthedocs.io/) |
| Charts | [Matplotlib](https://matplotlib.org/) |
| Data Processing | [Pandas](https://pandas.pydata.org/) & [NumPy](https://numpy.org/) |
| Scheduling | [schedule](https://schedule.readthedocs.io/) |
| Icons | [Lucide Icons](https://lucide.dev/) (MIT) |

---

<p align="center">
  Built with ❤️ for the developer community.<br/>
  <strong>NewsScrape Pro</strong> — Professional news intelligence at your fingertips.
</p>
