from __future__ import annotations

import threading
import tkinter as tk
import webbrowser
from datetime import datetime
from pathlib import Path
from tkinter import filedialog, messagebox
from typing import Any, Callable, Dict, List, Optional, TYPE_CHECKING

import customtkinter as ctk
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from matplotlib.figure import Figure

from analytics import AnalyticsEngine
from database import DatabaseManager
from exporter import DataExporter
from filters import HeadlineFilter
from logger import get_logger
from scheduler import ScrapeScheduler
from scraper import ScraperEngine
from settings import Settings
from utils import now_display, truncate, open_in_browser

if TYPE_CHECKING:
    pass

log = get_logger(__name__)

_ACCENT = "#4E79A7"
_ACCENT_HOVER = "#3A6291"
_SUCCESS = "#59A14F"
_WARNING = "#F28E2B"
_DANGER = "#E15759"
_CARD_DARK = "#16213e"
_CARD_LIGHT = "#f0f2f5"
_SIDEBAR_DARK = "#0f3460"
_SIDEBAR_LIGHT = "#1a5276"


def _run_in_thread(fn: Callable, callback: Optional[Callable] = None) -> threading.Thread:
    def wrapper():
        result = fn()
        if callback:
            callback(result)
    t = threading.Thread(target=wrapper, daemon=True)
    t.start()
    return t


class Sidebar(ctk.CTkFrame):
    _ITEMS = [
        ("Dashboard",    "house"),
        ("Scraper",      "newspaper"),
        ("Search",       "search"),
        ("Analytics",    "chart"),
        ("Export",       "save"),
        ("Settings",     "gear"),
        ("About",        "info"),
    ]

    _ICONS = {
        "house":     "\U0001F3E0",
        "newspaper": "\U0001F4F0",
        "search":    "\U0001F50D",
        "chart":     "\U0001F4CA",
        "save":      "\U0001F4BE",
        "gear":      "\u2699\uFE0F",
        "info":      "\u2139\uFE0F",
    }

    def __init__(self, master: ctk.CTk, on_navigate: Callable[[str], None], **kw):
        super().__init__(master, width=220, corner_radius=0, **kw)
        self.pack_propagate(False)
        self._on_navigate = on_navigate
        self._buttons: Dict[str, ctk.CTkButton] = {}
        self._active: str = "Dashboard"

        title_frame = ctk.CTkFrame(self, fg_color="transparent")
        title_frame.pack(pady=(24, 4), padx=16, fill="x")
        ctk.CTkLabel(title_frame, text="NewsScrape", font=ctk.CTkFont(size=22, weight="bold"), text_color=_ACCENT).pack(anchor="w")
        ctk.CTkLabel(title_frame, text="Pro", font=ctk.CTkFont(size=14), text_color="gray").pack(anchor="w")

        sep = ctk.CTkFrame(self, height=1, fg_color="gray40")
        sep.pack(fill="x", padx=16, pady=(12, 12))

        for label, icon_key in self._ITEMS:
            icon = self._ICONS.get(icon_key, "")
            btn = ctk.CTkButton(
                self, text=f"  {icon}  {label}", font=ctk.CTkFont(size=14),
                height=40, corner_radius=8, anchor="w", fg_color="transparent",
                text_color=("gray10", "gray90"), hover_color=("gray75", "gray30"),
                command=lambda l=label: self._navigate(l),
            )
            btn.pack(fill="x", padx=12, pady=3)
            self._buttons[label] = btn

        self._highlight("Dashboard")

    def _navigate(self, label: str) -> None:
        self._highlight(label)
        self._on_navigate(label)

    def _highlight(self, label: str) -> None:
        for name, btn in self._buttons.items():
            if name == label:
                btn.configure(fg_color=_ACCENT, text_color="white")
            else:
                btn.configure(fg_color="transparent", text_color=("gray10", "gray90"))
        self._active = label


class StatusBar(ctk.CTkFrame):
    def __init__(self, master: ctk.CTk, **kw):
        super().__init__(master, height=32, corner_radius=0, **kw)
        self.pack_propagate(False)

        self._label = ctk.CTkLabel(self, text="Ready", font=ctk.CTkFont(size=12), anchor="w")
        self._label.pack(side="left", padx=12)

        self._progress = ctk.CTkProgressBar(self, width=160, height=12)
        self._progress.pack(side="right", padx=12)
        self._progress.set(0)

    def set_message(self, msg: str) -> None:
        self._label.configure(text=msg)

    def set_progress(self, value: float) -> None:
        self._progress.set(value / 100.0)

    def reset(self) -> None:
        self._label.configure(text="Ready")
        self._progress.set(0)


class StatCard(ctk.CTkFrame):
    def __init__(self, master, icon: str, value: str, label: str, accent: str = _ACCENT, **kw):
        super().__init__(master, corner_radius=12, **kw)
        inner = ctk.CTkFrame(self, fg_color="transparent")
        inner.pack(padx=16, pady=14, fill="both", expand=True)

        ctk.CTkLabel(inner, text=icon, font=ctk.CTkFont(size=28)).pack(anchor="w")
        self._value_label = ctk.CTkLabel(inner, text=value, font=ctk.CTkFont(size=26, weight="bold"), text_color=accent)
        self._value_label.pack(anchor="w", pady=(6, 0))
        ctk.CTkLabel(inner, text=label, font=ctk.CTkFont(size=12), text_color="gray").pack(anchor="w")

    def set_value(self, value: str) -> None:
        self._value_label.configure(text=value)


class DashboardPage(ctk.CTkFrame):
    def __init__(self, master, app: "App", **kw):
        super().__init__(master, fg_color="transparent", **kw)
        self.app = app

        header = ctk.CTkFrame(self, fg_color="transparent")
        header.pack(fill="x", padx=20, pady=(16, 8))
        ctk.CTkLabel(header, text="Dashboard", font=ctk.CTkFont(size=24, weight="bold")).pack(side="left")
        ctk.CTkButton(header, text="Refresh", width=100, command=self.refresh, fg_color=_ACCENT, hover_color=_ACCENT_HOVER).pack(side="right")

        self._cards_frame = ctk.CTkFrame(self, fg_color="transparent")
        self._cards_frame.pack(fill="x", padx=20, pady=8)
        for i in range(4):
            self._cards_frame.columnconfigure(i, weight=1)

        self._card_total = StatCard(self._cards_frame, "\U0001F4F0", "0", "Total Headlines", _ACCENT)
        self._card_total.grid(row=0, column=0, padx=6, pady=6, sticky="nsew")
        self._card_today = StatCard(self._cards_frame, "\U0001F4C5", "0", "Today's Headlines", _SUCCESS)
        self._card_today.grid(row=0, column=1, padx=6, pady=6, sticky="nsew")
        self._card_sources = StatCard(self._cards_frame, "\U0001F310", "0", "Total Sources", _WARNING)
        self._card_sources.grid(row=0, column=2, padx=6, pady=6, sticky="nsew")
        self._card_last = StatCard(self._cards_frame, "\u23F0", "Never", "Last Scraped", _DANGER)
        self._card_last.grid(row=0, column=3, padx=6, pady=6, sticky="nsew")

        ctk.CTkLabel(self, text="Recent Headlines", font=ctk.CTkFont(size=16, weight="bold")).pack(anchor="w", padx=24, pady=(16, 4))
        self._recent_frame = ctk.CTkScrollableFrame(self, height=300)
        self._recent_frame.pack(fill="both", expand=True, padx=20, pady=(0, 12))

        ctk.CTkLabel(self, text="Latest Activity", font=ctk.CTkFont(size=16, weight="bold")).pack(anchor="w", padx=24, pady=(4, 4))
        self._activity_frame = ctk.CTkScrollableFrame(self, height=120)
        self._activity_frame.pack(fill="both", padx=20, pady=(0, 12))

    def refresh(self):
        db = self.app.db
        stats = db.get_statistics()
        self._card_total.set_value(str(stats.get("total_headlines", 0)))
        self._card_today.set_value(str(stats.get("today_headlines", 0)))
        self._card_sources.set_value(str(stats.get("total_sources", 0)))
        last = stats.get("last_scraped") or "Never"
        if last and last != "Never":
            last = last[:19].replace("T", " ")
        self._card_last.set_value(str(last))

        for w in self._recent_frame.winfo_children():
            w.destroy()
        recent = db.get_all_headlines(limit=15)
        for h in recent:
            row = ctk.CTkFrame(self._recent_frame, corner_radius=8)
            row.pack(fill="x", pady=2, padx=4)
            title_text = truncate(h.get("title", ""), 90)
            lbl = ctk.CTkLabel(row, text=f"  {h.get('source', '')}  |  {title_text}", font=ctk.CTkFont(size=12), anchor="w")
            lbl.pack(side="left", fill="x", expand=True, padx=8, pady=6)
            url = h.get("url", "")
            if url:
                ctk.CTkButton(row, text="Open", width=50, height=24, font=ctk.CTkFont(size=11),
                              fg_color=_ACCENT, hover_color=_ACCENT_HOVER,
                              command=lambda u=url: open_in_browser(u)).pack(side="right", padx=6)

        for w in self._activity_frame.winfo_children():
            w.destroy()
        activity = db.get_recent_activity(limit=10)
        for a in activity:
            text = f"[{a.get('created_at', '')[:19]}]  {a.get('action', '')} — {a.get('details', '')}"
            ctk.CTkLabel(self._activity_frame, text=text, font=ctk.CTkFont(size=11), anchor="w").pack(anchor="w", padx=8, pady=1)


class ScraperPage(ctk.CTkFrame):
    def __init__(self, master, app: "App", **kw):
        super().__init__(master, fg_color="transparent", **kw)
        self.app = app

        header = ctk.CTkFrame(self, fg_color="transparent")
        header.pack(fill="x", padx=20, pady=(16, 8))
        ctk.CTkLabel(header, text="News Scraper", font=ctk.CTkFont(size=24, weight="bold")).pack(side="left")

        src_frame = ctk.CTkFrame(self, corner_radius=10)
        src_frame.pack(fill="x", padx=20, pady=8)
        ctk.CTkLabel(src_frame, text="Select Sources:", font=ctk.CTkFont(size=13, weight="bold")).pack(anchor="w", padx=12, pady=(8, 4))

        self._source_vars: Dict[str, tk.BooleanVar] = {}
        chk_grid = ctk.CTkFrame(src_frame, fg_color="transparent")
        chk_grid.pack(fill="x", padx=12, pady=(0, 8))

        sources = self.app.scraper_engine.available_sources
        for i, src in enumerate(sources):
            var = tk.BooleanVar(value=src.get("enabled", True))
            self._source_vars[src["name"]] = var
            ctk.CTkCheckBox(
                chk_grid, text=src["name"], variable=var,
                font=ctk.CTkFont(size=12),
            ).grid(row=i // 4, column=i % 4, padx=8, pady=3, sticky="w")

        btn_frame = ctk.CTkFrame(self, fg_color="transparent")
        btn_frame.pack(fill="x", padx=20, pady=6)
        ctk.CTkButton(btn_frame, text="Scrape Selected", fg_color=_ACCENT, hover_color=_ACCENT_HOVER, command=self._scrape_selected).pack(side="left", padx=4)
        ctk.CTkButton(btn_frame, text="Scrape All", fg_color=_SUCCESS, hover_color="#4a8a42", command=self._scrape_all).pack(side="left", padx=4)
        ctk.CTkButton(btn_frame, text="Stop", fg_color=_DANGER, hover_color="#c44648", command=self._stop).pack(side="left", padx=4)
        ctk.CTkButton(btn_frame, text="Clear", fg_color="gray50", hover_color="gray40", command=self._clear_table).pack(side="left", padx=4)

        self._progress_label = ctk.CTkLabel(self, text="", font=ctk.CTkFont(size=12))
        self._progress_label.pack(anchor="w", padx=24, pady=(4, 0))
        self._progress_bar = ctk.CTkProgressBar(self, width=400, height=14)
        self._progress_bar.pack(anchor="w", padx=24, pady=(2, 8))
        self._progress_bar.set(0)

        table_frame = ctk.CTkFrame(self, corner_radius=10)
        table_frame.pack(fill="both", expand=True, padx=20, pady=(0, 12))

        columns = ("title", "source", "category", "author", "published", "url")
        self._tree = tk.ttk.Treeview(table_frame, columns=columns, show="headings", height=18)
        self._tree.heading("title", text="Title")
        self._tree.heading("source", text="Source")
        self._tree.heading("category", text="Category")
        self._tree.heading("author", text="Author")
        self._tree.heading("published", text="Published")
        self._tree.heading("url", text="URL")
        self._tree.column("title", width=350, minwidth=200)
        self._tree.column("source", width=100, minwidth=80)
        self._tree.column("category", width=90, minwidth=70)
        self._tree.column("author", width=100, minwidth=70)
        self._tree.column("published", width=140, minwidth=100)
        self._tree.column("url", width=200, minwidth=100)

        vsb = tk.ttk.Scrollbar(table_frame, orient="vertical", command=self._tree.yview)
        hsb = tk.ttk.Scrollbar(table_frame, orient="horizontal", command=self._tree.xview)
        self._tree.configure(yscrollcommand=vsb.set, xscrollcommand=hsb.set)

        self._tree.pack(side="left", fill="both", expand=True, padx=(8, 0), pady=8)
        vsb.pack(side="right", fill="y", pady=8)

        self._tree.bind("<Double-1>", self._on_double_click)

    def _scrape_selected(self):
        names = [n for n, v in self._source_vars.items() if v.get()]
        if not names:
            messagebox.showwarning("No Sources", "Please select at least one source.")
            return
        self._run_scrape(lambda: self.app.scraper_engine.scrape_selected(names, on_progress=self._on_progress))

    def _scrape_all(self):
        self._run_scrape(lambda: self.app.scraper_engine.scrape_all(on_progress=self._on_progress))

    def _run_scrape(self, fn):
        self._progress_bar.set(0)
        self._progress_label.configure(text="Scraping ...")
        self.app.status_bar.set_message("Scraping in progress ...")

        def task():
            results = fn()
            if results:
                inserted, skipped = self.app.db.insert_many(results)
                self.app.db.log_activity("scrape_completed", f"{inserted} new, {skipped} duplicates")
            self.after(0, lambda: self._on_scrape_done(results))

        _run_in_thread(task)

    def _on_progress(self, pct: float, msg: str):
        self.after(0, lambda: self._progress_bar.set(pct / 100.0))
        self.after(0, lambda: self._progress_label.configure(text=msg))
        self.after(0, lambda: self.app.status_bar.set_message(msg))

    def _on_scrape_done(self, results):
        self._progress_bar.set(1.0)
        self._progress_label.configure(text=f"Done — {len(results)} headlines collected")
        self.app.status_bar.set_message(f"Scrape complete: {len(results)} headlines")
        self._populate_table(results)

    def _populate_table(self, headlines):
        self._tree.delete(*self._tree.get_children())
        for h in headlines:
            self._tree.insert("", "end", values=(
                truncate(h.get("title", ""), 80),
                h.get("source", ""),
                h.get("category", ""),
                h.get("author", ""),
                (h.get("published_time") or "")[:19],
                h.get("url", ""),
            ))

    def _clear_table(self):
        self._tree.delete(*self._tree.get_children())
        self._progress_bar.set(0)
        self._progress_label.configure(text="")

    def _stop(self):
        self.app.scraper_engine.request_stop()
        self._progress_label.configure(text="Stop requested ...")
        self.app.status_bar.set_message("Stop requested")

    def _on_double_click(self, event):
        item = self._tree.selection()
        if item:
            values = self._tree.item(item[0], "values")
            if values and len(values) >= 6:
                open_in_browser(values[5])


class SearchPage(ctk.CTkFrame):
    def __init__(self, master, app: "App", **kw):
        super().__init__(master, fg_color="transparent", **kw)
        self.app = app

        header = ctk.CTkFrame(self, fg_color="transparent")
        header.pack(fill="x", padx=20, pady=(16, 8))
        ctk.CTkLabel(header, text="Search & Filter", font=ctk.CTkFont(size=24, weight="bold")).pack(side="left")

        search_frame = ctk.CTkFrame(self, corner_radius=10)
        search_frame.pack(fill="x", padx=20, pady=8)

        self._search_var = tk.StringVar()
        ctk.CTkEntry(search_frame, textvariable=self._search_var, placeholder_text="Search headlines ...", width=350, height=36, font=ctk.CTkFont(size=13)).pack(side="left", padx=(12, 6), pady=10)

        ctk.CTkLabel(search_frame, text="Source:", font=ctk.CTkFont(size=12)).pack(side="left", padx=(12, 4))
        self._source_filter = ctk.CTkComboBox(search_frame, values=["All"] + self.app.db.get_distinct_sources(), width=140, font=ctk.CTkFont(size=12))
        self._source_filter.set("All")
        self._source_filter.pack(side="left", padx=4)

        ctk.CTkLabel(search_frame, text="Category:", font=ctk.CTkFont(size=12)).pack(side="left", padx=(12, 4))
        self._cat_filter = ctk.CTkComboBox(search_frame, values=["All"] + self.app.db.get_distinct_categories(), width=130, font=ctk.CTkFont(size=12))
        self._cat_filter.set("All")
        self._cat_filter.pack(side="left", padx=4)

        ctk.CTkButton(search_frame, text="Search", width=80, fg_color=_ACCENT, hover_color=_ACCENT_HOVER, command=self._search).pack(side="left", padx=8, pady=10)

        sort_frame = ctk.CTkFrame(self, fg_color="transparent")
        sort_frame.pack(fill="x", padx=20, pady=4)
        ctk.CTkButton(sort_frame, text="A-Z", width=60, fg_color="gray50", hover_color="gray40", command=lambda: self._sort("alpha")).pack(side="left", padx=3)
        ctk.CTkButton(sort_frame, text="Latest", width=60, fg_color="gray50", hover_color="gray40", command=lambda: self._sort("latest")).pack(side="left", padx=3)
        ctk.CTkButton(sort_frame, text="Oldest", width=60, fg_color="gray50", hover_color="gray40", command=lambda: self._sort("oldest")).pack(side="left", padx=3)
        ctk.CTkButton(sort_frame, text="Remove Duplicates", width=130, fg_color=_WARNING, hover_color="#d97d20", command=self._dedup).pack(side="left", padx=8)
        self._result_count = ctk.CTkLabel(sort_frame, text="", font=ctk.CTkFont(size=12))
        self._result_count.pack(side="right", padx=12)

        table_frame = ctk.CTkFrame(self, corner_radius=10)
        table_frame.pack(fill="both", expand=True, padx=20, pady=(4, 12))

        columns = ("title", "source", "category", "author", "published", "url")
        self._tree = tk.ttk.Treeview(table_frame, columns=columns, show="headings", height=20)
        for col, w in [("title", 350), ("source", 100), ("category", 90), ("author", 100), ("published", 140), ("url", 200)]:
            self._tree.heading(col, text=col.title())
            self._tree.column(col, width=w, minwidth=70)

        vsb = tk.ttk.Scrollbar(table_frame, orient="vertical", command=self._tree.yview)
        self._tree.configure(yscrollcommand=vsb.set)
        self._tree.pack(side="left", fill="both", expand=True, padx=(8, 0), pady=8)
        vsb.pack(side="right", fill="y", pady=8)
        self._tree.bind("<Double-1>", self._on_double_click)

        self._current_results: List[Dict] = []

    def refresh_filters(self):
        self._source_filter.configure(values=["All"] + self.app.db.get_distinct_sources())
        self._cat_filter.configure(values=["All"] + self.app.db.get_distinct_categories())

    def _search(self):
        keyword = self._search_var.get().strip()
        source = self._source_filter.get()
        category = self._cat_filter.get()

        src = source if source != "All" else None
        cat = category if category != "All" else None

        results = self.app.db.search(keyword or "", source=src, category=cat, limit=500)
        self._current_results = results

        if keyword:
            self.app.db.save_search(keyword)

        self._populate(results)
        self._result_count.configure(text=f"{len(results)} results")

    def _sort(self, mode: str):
        f = HeadlineFilter(self._current_results)
        if mode == "alpha":
            f.sort_alphabetically()
        elif mode == "latest":
            f.sort_by_latest()
        elif mode == "oldest":
            f.sort_by_oldest()
        self._current_results = f.results()
        self._populate(self._current_results)

    def _dedup(self):
        f = HeadlineFilter(self._current_results).deduplicate()
        self._current_results = f.results()
        self._populate(self._current_results)
        self._result_count.configure(text=f"{len(self._current_results)} results (deduped)")

    def _populate(self, data):
        self._tree.delete(*self._tree.get_children())
        for h in data:
            self._tree.insert("", "end", values=(
                truncate(h.get("title", ""), 80),
                h.get("source", ""),
                h.get("category", ""),
                h.get("author", ""),
                (h.get("published_time") or "")[:19],
                h.get("url", ""),
            ))

    def _on_double_click(self, event):
        item = self._tree.selection()
        if item:
            values = self._tree.item(item[0], "values")
            if values and len(values) >= 6:
                open_in_browser(values[5])


class AnalyticsPage(ctk.CTkFrame):
    def __init__(self, master, app: "App", **kw):
        super().__init__(master, fg_color="transparent", **kw)
        self.app = app

        header = ctk.CTkFrame(self, fg_color="transparent")
        header.pack(fill="x", padx=20, pady=(16, 8))
        ctk.CTkLabel(header, text="Analytics", font=ctk.CTkFont(size=24, weight="bold")).pack(side="left")
        ctk.CTkButton(header, text="Refresh Charts", width=120, fg_color=_ACCENT, hover_color=_ACCENT_HOVER, command=self.refresh).pack(side="right")

        self._chart_area = ctk.CTkScrollableFrame(self)
        self._chart_area.pack(fill="both", expand=True, padx=20, pady=(0, 12))
        self._chart_area.columnconfigure(0, weight=1)
        self._chart_area.columnconfigure(1, weight=1)

    def refresh(self):
        for w in self._chart_area.winfo_children():
            w.destroy()

        dark = self.app.cfg.theme == "dark"
        engine = AnalyticsEngine(dark_mode=dark)
        db = self.app.db

        src_data = db.get_headlines_per_source()
        cat_data = db.get_category_distribution()
        daily_data = db.get_daily_activity(30)
        all_headlines = db.get_all_headlines(limit=2000)
        kw_data = HeadlineFilter(all_headlines).top_keywords(15)

        charts = []
        if src_data:
            charts.append(("Headlines per Source", engine.headlines_per_source(src_data)))
        if cat_data:
            charts.append(("Category Distribution", engine.category_distribution(cat_data)))
        if kw_data:
            charts.append(("Top Keywords", engine.top_keywords(kw_data)))
        if daily_data:
            charts.append(("Daily Activity", engine.daily_activity(daily_data)))
            charts.append(("Weekly Trend", engine.weekly_trend(daily_data)))

        if not charts:
            ctk.CTkLabel(self._chart_area, text="No data to visualize. Scrape some headlines first!",
                         font=ctk.CTkFont(size=16), text_color="gray").grid(row=0, column=0, columnspan=2, pady=40)
            return

        for idx, (title, fig) in enumerate(charts):
            frame = ctk.CTkFrame(self._chart_area, corner_radius=10)
            frame.grid(row=idx // 2, column=idx % 2, padx=8, pady=8, sticky="nsew")
            ctk.CTkLabel(frame, text=title, font=ctk.CTkFont(size=14, weight="bold")).pack(pady=(8, 0))
            canvas = FigureCanvasTkAgg(fig, master=frame)
            canvas.draw()
            canvas.get_tk_widget().pack(fill="both", expand=True, padx=8, pady=(4, 8))


class ExportPage(ctk.CTkFrame):
    def __init__(self, master, app: "App", **kw):
        super().__init__(master, fg_color="transparent", **kw)
        self.app = app

        header = ctk.CTkFrame(self, fg_color="transparent")
        header.pack(fill="x", padx=20, pady=(16, 8))
        ctk.CTkLabel(header, text="Export Data", font=ctk.CTkFont(size=24, weight="bold")).pack(side="left")

        options = ctk.CTkFrame(self, corner_radius=10)
        options.pack(fill="x", padx=20, pady=12)
        ctk.CTkLabel(options, text="Export all headlines from the database in your preferred format.", font=ctk.CTkFont(size=13)).pack(anchor="w", padx=16, pady=(12, 8))

        btn_frame = ctk.CTkFrame(options, fg_color="transparent")
        btn_frame.pack(fill="x", padx=16, pady=(4, 16))

        ctk.CTkButton(btn_frame, text="\U0001F4C4  Export CSV", width=160, height=44, font=ctk.CTkFont(size=14), fg_color="#2E86AB", hover_color="#256d8a", command=self._export_csv).pack(side="left", padx=8)
        ctk.CTkButton(btn_frame, text="\U0001F4CB  Export JSON", width=160, height=44, font=ctk.CTkFont(size=14), fg_color="#A23B72", hover_color="#8a3261", command=self._export_json).pack(side="left", padx=8)
        ctk.CTkButton(btn_frame, text="\U0001F4CA  Export Excel", width=160, height=44, font=ctk.CTkFont(size=14), fg_color="#59A14F", hover_color="#4a8a42", command=self._export_excel).pack(side="left", padx=8)
        ctk.CTkButton(btn_frame, text="\U0001F4E6  Export All Formats", width=180, height=44, font=ctk.CTkFont(size=14), fg_color=_ACCENT, hover_color=_ACCENT_HOVER, command=self._export_all).pack(side="left", padx=8)

        self._status = ctk.CTkLabel(self, text="", font=ctk.CTkFont(size=13))
        self._status.pack(anchor="w", padx=28, pady=8)

        ctk.CTkLabel(self, text="Export Directory", font=ctk.CTkFont(size=16, weight="bold")).pack(anchor="w", padx=24, pady=(16, 4))
        dir_text = str(self.app.cfg.export_folder)
        self._dir_label = ctk.CTkLabel(self, text=dir_text, font=ctk.CTkFont(size=12), text_color="gray")
        self._dir_label.pack(anchor="w", padx=28)

    def _export_csv(self):
        self._do_export("csv")

    def _export_json(self):
        self._do_export("json")

    def _export_excel(self):
        self._do_export("excel")

    def _export_all(self):
        data = self.app.db.get_all_as_dicts()
        if not data:
            self._status.configure(text="No data to export.", text_color=_DANGER)
            return
        exp = DataExporter()
        paths = exp.export_all(data)
        self.app.db.log_activity("export_all", f"{len(data)} rows to CSV, JSON, Excel")
        self._status.configure(text=f"Exported {len(data)} rows to all 3 formats.", text_color=_SUCCESS)

    def _do_export(self, fmt: str):
        data = self.app.db.get_all_as_dicts()
        if not data:
            self._status.configure(text="No data to export.", text_color=_DANGER)
            return
        exp = DataExporter()
        if fmt == "csv":
            path = exp.to_csv(data)
        elif fmt == "json":
            path = exp.to_json(data)
        else:
            path = exp.to_excel(data)
        self.app.db.log_activity(f"export_{fmt}", f"{len(data)} rows -> {path.name}")
        self._status.configure(text=f"Exported {len(data)} rows to {path.name}", text_color=_SUCCESS)


class SettingsPage(ctk.CTkFrame):
    def __init__(self, master, app: "App", **kw):
        super().__init__(master, fg_color="transparent", **kw)
        self.app = app

        header = ctk.CTkFrame(self, fg_color="transparent")
        header.pack(fill="x", padx=20, pady=(16, 8))
        ctk.CTkLabel(header, text="Settings", font=ctk.CTkFont(size=24, weight="bold")).pack(side="left")

        scroll = ctk.CTkScrollableFrame(self)
        scroll.pack(fill="both", expand=True, padx=20, pady=(0, 12))

        self._add_section(scroll, "Appearance")
        theme_frame = ctk.CTkFrame(scroll, fg_color="transparent")
        theme_frame.pack(fill="x", padx=12, pady=4)
        ctk.CTkLabel(theme_frame, text="Theme:", font=ctk.CTkFont(size=13)).pack(side="left", padx=(0, 8))
        self._theme_var = ctk.StringVar(value=self.app.cfg.theme.capitalize())
        ctk.CTkSegmentedButton(theme_frame, values=["Dark", "Light", "System"], variable=self._theme_var, command=self._on_theme_change).pack(side="left")

        self._add_section(scroll, "Scraper")
        self._timeout_var = tk.IntVar(value=self.app.cfg.request_timeout)
        self._add_setting_row(scroll, "Request Timeout (s):", self._timeout_var, 5, 60)
        self._retry_var = tk.IntVar(value=self.app.cfg.retry_count)
        self._add_setting_row(scroll, "Retry Count:", self._retry_var, 1, 10)
        self._delay_var = tk.DoubleVar(value=self.app.cfg.request_delay)
        self._add_setting_row(scroll, "Request Delay (s):", self._delay_var, 0.5, 10.0)

        self._add_section(scroll, "Scheduler")
        sched_frame = ctk.CTkFrame(scroll, fg_color="transparent")
        sched_frame.pack(fill="x", padx=12, pady=4)
        ctk.CTkLabel(sched_frame, text="Auto-Scrape Interval:", font=ctk.CTkFont(size=13)).pack(side="left")
        self._interval_var = ctk.StringVar(value=str(self.app.cfg.scheduler_interval))
        ctk.CTkComboBox(sched_frame, values=["15", "30", "60", "120", "360"], variable=self._interval_var, width=100).pack(side="left", padx=8)
        ctk.CTkLabel(sched_frame, text="minutes", font=ctk.CTkFont(size=12), text_color="gray").pack(side="left")

        sched_btn_frame = ctk.CTkFrame(scroll, fg_color="transparent")
        sched_btn_frame.pack(fill="x", padx=12, pady=4)
        ctk.CTkButton(sched_btn_frame, text="Start Scheduler", fg_color=_SUCCESS, hover_color="#4a8a42", command=self._start_scheduler).pack(side="left", padx=4)
        ctk.CTkButton(sched_btn_frame, text="Stop Scheduler", fg_color=_DANGER, hover_color="#c44648", command=self._stop_scheduler).pack(side="left", padx=4)
        self._sched_status = ctk.CTkLabel(sched_btn_frame, text="Stopped", font=ctk.CTkFont(size=12), text_color="gray")
        self._sched_status.pack(side="left", padx=12)

        self._add_section(scroll, "Database")
        db_frame = ctk.CTkFrame(scroll, fg_color="transparent")
        db_frame.pack(fill="x", padx=12, pady=4)
        ctk.CTkButton(db_frame, text="Backup Database", fg_color=_ACCENT, hover_color=_ACCENT_HOVER, command=self._backup_db).pack(side="left", padx=4)
        ctk.CTkButton(db_frame, text="Remove Duplicates", fg_color=_WARNING, hover_color="#d97d20", command=self._remove_dupes).pack(side="left", padx=4)
        ctk.CTkButton(db_frame, text="Clear All Data", fg_color=_DANGER, hover_color="#c44648", command=self._clear_db).pack(side="left", padx=4)
        self._db_status = ctk.CTkLabel(db_frame, text="", font=ctk.CTkFont(size=12))
        self._db_status.pack(side="left", padx=12)

        ctk.CTkButton(scroll, text="Save Settings", fg_color=_ACCENT, hover_color=_ACCENT_HOVER, height=40, font=ctk.CTkFont(size=14, weight="bold"), command=self._save).pack(pady=16, padx=12, anchor="w")

    def _add_section(self, parent, title):
        ctk.CTkLabel(parent, text=title, font=ctk.CTkFont(size=16, weight="bold")).pack(anchor="w", padx=12, pady=(16, 4))
        sep = ctk.CTkFrame(parent, height=1, fg_color="gray40")
        sep.pack(fill="x", padx=12, pady=(0, 8))

    def _add_setting_row(self, parent, label, var, from_, to_):
        row = ctk.CTkFrame(parent, fg_color="transparent")
        row.pack(fill="x", padx=12, pady=3)
        ctk.CTkLabel(row, text=label, font=ctk.CTkFont(size=13), width=180, anchor="w").pack(side="left")
        ctk.CTkSlider(row, from_=from_, to=to_, variable=var, width=200).pack(side="left", padx=8)
        ctk.CTkLabel(row, textvariable=var, font=ctk.CTkFont(size=12), width=50).pack(side="left")

    def _on_theme_change(self, value: str):
        theme = value.lower()
        ctk.set_appearance_mode(theme)
        self.app.cfg.theme = theme

    def _save(self):
        cfg = self.app.cfg
        cfg.request_timeout = int(self._timeout_var.get())
        cfg.retry_count = int(self._retry_var.get())
        cfg.request_delay = float(self._delay_var.get())
        try:
            cfg.scheduler_interval = int(self._interval_var.get())
        except ValueError:
            pass
        self.app.status_bar.set_message("Settings saved.")

    def _start_scheduler(self):
        try:
            interval = int(self._interval_var.get())
        except ValueError:
            interval = 60
        self.app.start_scheduler(interval)
        self._sched_status.configure(text=f"Running (every {interval} min)", text_color=_SUCCESS)

    def _stop_scheduler(self):
        self.app.stop_scheduler()
        self._sched_status.configure(text="Stopped", text_color="gray")

    def _backup_db(self):
        path = self.app.db.backup()
        if path:
            self._db_status.configure(text=f"Backed up: {path.name}", text_color=_SUCCESS)
        else:
            self._db_status.configure(text="Backup failed", text_color=_DANGER)

    def _remove_dupes(self):
        removed = self.app.db.remove_duplicates()
        self._db_status.configure(text=f"Removed {removed} duplicates", text_color=_SUCCESS)

    def _clear_db(self):
        if messagebox.askyesno("Confirm", "Delete ALL headlines from the database?"):
            count = self.app.db.delete_all_headlines()
            self._db_status.configure(text=f"Deleted {count} headlines", text_color=_WARNING)


class AboutPage(ctk.CTkFrame):
    def __init__(self, master, app: "App", **kw):
        super().__init__(master, fg_color="transparent", **kw)
        self.app = app

        center = ctk.CTkFrame(self, fg_color="transparent")
        center.place(relx=0.5, rely=0.4, anchor="center")

        ctk.CTkLabel(center, text="\U0001F4F0", font=ctk.CTkFont(size=56)).pack(pady=(0, 8))
        ctk.CTkLabel(center, text="NewsScrape Pro", font=ctk.CTkFont(size=32, weight="bold"), text_color=_ACCENT).pack()
        ctk.CTkLabel(center, text="Advanced Multi-Source News Headline Scraper", font=ctk.CTkFont(size=14), text_color="gray").pack(pady=(4, 16))
        ctk.CTkLabel(center, text=f"Version {app.cfg.app_version}", font=ctk.CTkFont(size=13)).pack()
        ctk.CTkLabel(center, text="Built with Python, CustomTkinter, BeautifulSoup & Matplotlib", font=ctk.CTkFont(size=12), text_color="gray").pack(pady=4)

        sep = ctk.CTkFrame(center, height=1, fg_color="gray40", width=300)
        sep.pack(pady=16)

        ctk.CTkLabel(center, text="Designed for portfolio demonstration.", font=ctk.CTkFont(size=12), text_color="gray").pack()
        ctk.CTkLabel(center, text="Respectful scraping: honours robots.txt, uses delays & UA rotation.", font=ctk.CTkFont(size=11), text_color="gray").pack(pady=2)

        btn_frame = ctk.CTkFrame(center, fg_color="transparent")
        btn_frame.pack(pady=16)
        ctk.CTkButton(btn_frame, text="GitHub", width=100, fg_color=_ACCENT, hover_color=_ACCENT_HOVER, command=lambda: webbrowser.open("https://github.com/sohamfegade")).pack(side="left", padx=6)
        ctk.CTkButton(btn_frame, text="LinkedIn", width=100, fg_color="#0A66C2", hover_color="#084c91", command=lambda: webbrowser.open("https://linkedin.com/in/sohamfegade")).pack(side="left", padx=6)


class App(ctk.CTk):
    def __init__(self, settings: Settings) -> None:
        super().__init__()
        self.cfg = settings
        self.title(f"{settings.app_name} v{settings.app_version}")
        self.geometry(f"{settings.window_width}x{settings.window_height}")
        self.minsize(1000, 600)

        ctk.set_appearance_mode(settings.theme)
        ctk.set_default_color_theme("blue")
        self._style_treeview()

        self.db = DatabaseManager()
        self.scraper_engine = ScraperEngine()
        self._exporter = DataExporter()
        self._scheduler: Optional[ScrapeScheduler] = None

        self._build_layout()
        self._navigate("Dashboard")
        self.pages["Dashboard"].refresh()

        self.protocol("WM_DELETE_WINDOW", self._on_close)
        log.info("GUI initialised.")

    def _build_layout(self) -> None:
        self.sidebar = Sidebar(self, on_navigate=self._navigate)
        self.sidebar.pack(side="left", fill="y")

        main_container = ctk.CTkFrame(self, fg_color="transparent", corner_radius=0)
        main_container.pack(side="right", fill="both", expand=True)

        self._content = ctk.CTkFrame(main_container, fg_color="transparent", corner_radius=0)
        self._content.pack(fill="both", expand=True)

        self.status_bar = StatusBar(main_container)
        self.status_bar.pack(side="bottom", fill="x")

        self.pages: Dict[str, ctk.CTkFrame] = {
            "Dashboard": DashboardPage(self._content, self),
            "Scraper": ScraperPage(self._content, self),
            "Search": SearchPage(self._content, self),
            "Analytics": AnalyticsPage(self._content, self),
            "Export": ExportPage(self._content, self),
            "Settings": SettingsPage(self._content, self),
            "About": AboutPage(self._content, self),
        }

    def _navigate(self, page_name: str) -> None:
        for page in self.pages.values():
            page.pack_forget()
        page = self.pages.get(page_name)
        if page:
            page.pack(fill="both", expand=True)
            if page_name == "Dashboard":
                page.refresh()
            elif page_name == "Analytics":
                page.refresh()
            elif page_name == "Search":
                page.refresh_filters()

    def _style_treeview(self) -> None:
        style = tk.ttk.Style()
        style.theme_use("clam")
        dark = self.cfg.theme == "dark"
        bg = "#1a1a2e" if dark else "#ffffff"
        fg = "#e0e0e0" if dark else "#333333"
        sel_bg = _ACCENT
        field_bg = "#16213e" if dark else "#f8f9fa"
        header_bg = "#0f3460" if dark else "#d6e4f0"
        style.configure("Treeview", background=field_bg, foreground=fg, fieldbackground=field_bg, rowheight=28, font=("Segoe UI", 10))
        style.configure("Treeview.Heading", background=header_bg, foreground=fg, font=("Segoe UI", 10, "bold"))
        style.map("Treeview", background=[("selected", sel_bg)], foreground=[("selected", "white")])

    def start_scheduler(self, interval: int) -> None:
        if self._scheduler and self._scheduler.is_running:
            self._scheduler.stop()

        def scrape_job():
            results = self.scraper_engine.scrape_all()
            if results:
                self.db.insert_many(results)
                self.db.log_activity("scheduled_scrape", f"{len(results)} headlines")
            self.after(0, lambda: self.status_bar.set_message(f"Scheduled scrape: {len(results)} headlines"))

        self._scheduler = ScrapeScheduler(scrape_fn=scrape_job, on_tick=lambda msg: self.after(0, lambda: self.status_bar.set_message(msg)))
        self._scheduler.start(interval)
        self.status_bar.set_message(f"Scheduler started: every {interval} min")

    def stop_scheduler(self) -> None:
        if self._scheduler:
            self._scheduler.stop()
            self.status_bar.set_message("Scheduler stopped.")

    def _on_close(self) -> None:
        if self._scheduler and self._scheduler.is_running:
            self._scheduler.stop()
        self.db.log_activity("app_closed", "Application shut down normally.")
        log.info("Application closed.")
        self.destroy()


def launch(settings: Settings) -> None:
    app = App(settings)
    app.mainloop()
