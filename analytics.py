from __future__ import annotations

from collections import Counter
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple

import matplotlib
matplotlib.use("Agg")

import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from matplotlib.figure import Figure

from logger import get_logger

log = get_logger(__name__)

_PALETTE = [
    "#4E79A7", "#F28E2B", "#E15759", "#76B7B2",
    "#59A14F", "#EDC949", "#AF7AA1", "#FF9DA7",
    "#9C755F", "#BAB0AC", "#6B9BD2", "#D4A6C8",
]

_DARK_BG = "#1a1a2e"
_DARK_FG = "#e0e0e0"
_LIGHT_BG = "#ffffff"
_LIGHT_FG = "#333333"


def _apply_theme(fig: Figure, ax: Any, dark: bool = True) -> None:
    bg = _DARK_BG if dark else _LIGHT_BG
    fg = _DARK_FG if dark else _LIGHT_FG

    fig.patch.set_facecolor(bg)
    ax.set_facecolor(bg)
    ax.tick_params(colors=fg, labelsize=9)
    ax.xaxis.label.set_color(fg)
    ax.yaxis.label.set_color(fg)
    ax.title.set_color(fg)
    for spine in ax.spines.values():
        spine.set_color(fg)
        spine.set_alpha(0.3)


class AnalyticsEngine:
    def __init__(self, dark_mode: bool = True) -> None:
        self._dark = dark_mode

    def headlines_per_source(self, source_data: List[Dict[str, Any]], figsize: Tuple[float, float] = (7, 4)) -> Figure:
        fig, ax = plt.subplots(figsize=figsize)
        _apply_theme(fig, ax, self._dark)

        sources = [d["source"] for d in source_data][::-1]
        counts = [d["count"] for d in source_data][::-1]
        colours = [_PALETTE[i % len(_PALETTE)] for i in range(len(sources))][::-1]

        bars = ax.barh(sources, counts, color=colours, height=0.6, edgecolor="none")
        ax.set_xlabel("Headlines")
        ax.set_title("Headlines per Source", fontsize=13, fontweight="bold", pad=12)

        fg = _DARK_FG if self._dark else _LIGHT_FG
        for bar, val in zip(bars, counts):
            ax.text(
                bar.get_width() + 0.3, bar.get_y() + bar.get_height() / 2,
                str(val), va="center", fontsize=9, color=fg,
            )

        ax.set_xlim(0, max(counts, default=1) * 1.15)
        fig.tight_layout()
        plt.close(fig)
        return fig

    def category_distribution(self, category_data: List[Dict[str, Any]], figsize: Tuple[float, float] = (6, 4)) -> Figure:
        fig, ax = plt.subplots(figsize=figsize)
        _apply_theme(fig, ax, self._dark)

        labels = [d["category"] for d in category_data]
        sizes = [d["count"] for d in category_data]
        colours = [_PALETTE[i % len(_PALETTE)] for i in range(len(labels))]

        fg = _DARK_FG if self._dark else _LIGHT_FG

        wedges, texts, autotexts = ax.pie(
            sizes, labels=labels, colors=colours, autopct="%1.0f%%",
            startangle=140, pctdistance=0.78,
            textprops={"fontsize": 9, "color": fg},
        )
        for at in autotexts:
            at.set_fontsize(8)
            at.set_color(fg)

        centre = plt.Circle((0, 0), 0.55, fc=_DARK_BG if self._dark else _LIGHT_BG)
        ax.add_patch(centre)

        ax.set_title("Category Distribution", fontsize=13, fontweight="bold", pad=12)
        fig.tight_layout()
        plt.close(fig)
        return fig

    def top_keywords(self, keyword_data: List[Tuple[str, int]], figsize: Tuple[float, float] = (7, 4)) -> Figure:
        fig, ax = plt.subplots(figsize=figsize)
        _apply_theme(fig, ax, self._dark)

        if not keyword_data:
            ax.text(0.5, 0.5, "No data", ha="center", va="center",
                    fontsize=14, color=_DARK_FG if self._dark else _LIGHT_FG)
            plt.close(fig)
            return fig

        words = [w for w, _ in keyword_data][::-1]
        freqs = [c for _, c in keyword_data][::-1]
        colours = [_PALETTE[i % len(_PALETTE)] for i in range(len(words))][::-1]

        bars = ax.barh(words, freqs, color=colours, height=0.6)
        ax.set_xlabel("Frequency")
        ax.set_title("Most Frequent Keywords", fontsize=13, fontweight="bold", pad=12)

        fg = _DARK_FG if self._dark else _LIGHT_FG
        for bar, val in zip(bars, freqs):
            ax.text(
                bar.get_width() + 0.2, bar.get_y() + bar.get_height() / 2,
                str(val), va="center", fontsize=9, color=fg,
            )

        ax.set_xlim(0, max(freqs, default=1) * 1.15)
        fig.tight_layout()
        plt.close(fig)
        return fig

    def daily_activity(self, daily_data: List[Dict[str, Any]], figsize: Tuple[float, float] = (8, 4)) -> Figure:
        fig, ax = plt.subplots(figsize=figsize)
        _apply_theme(fig, ax, self._dark)

        if not daily_data:
            ax.text(0.5, 0.5, "No data", ha="center", va="center",
                    fontsize=14, color=_DARK_FG if self._dark else _LIGHT_FG)
            plt.close(fig)
            return fig

        dates = [datetime.strptime(d["date"], "%Y-%m-%d") for d in daily_data]
        counts = [d["count"] for d in daily_data]

        ax.plot(dates, counts, color=_PALETTE[0], linewidth=2, marker="o",
                markersize=5, markerfacecolor=_PALETTE[1])
        ax.fill_between(dates, counts, alpha=0.15, color=_PALETTE[0])
        ax.set_xlabel("Date")
        ax.set_ylabel("Headlines")
        ax.set_title("Daily Scraping Activity", fontsize=13, fontweight="bold", pad=12)

        ax.xaxis.set_major_formatter(mdates.DateFormatter("%b %d"))
        fig.autofmt_xdate(rotation=30)
        fig.tight_layout()
        plt.close(fig)
        return fig

    def weekly_trend(self, daily_data: List[Dict[str, Any]], figsize: Tuple[float, float] = (8, 4)) -> Figure:
        fig, ax = plt.subplots(figsize=figsize)
        _apply_theme(fig, ax, self._dark)

        if not daily_data:
            ax.text(0.5, 0.5, "No data", ha="center", va="center",
                    fontsize=14, color=_DARK_FG if self._dark else _LIGHT_FG)
            plt.close(fig)
            return fig

        weekly: Dict[str, int] = {}
        for d in daily_data:
            dt = datetime.strptime(d["date"], "%Y-%m-%d")
            iso = dt.isocalendar()
            week_label = f"W{iso[1]:02d}"
            weekly[week_label] = weekly.get(week_label, 0) + d["count"]

        weeks = list(weekly.keys())
        totals = list(weekly.values())
        colours = [_PALETTE[i % len(_PALETTE)] for i in range(len(weeks))]

        ax.bar(weeks, totals, color=colours, width=0.5, edgecolor="none")
        ax.set_xlabel("Week")
        ax.set_ylabel("Headlines")
        ax.set_title("Weekly Scraping Trend", fontsize=13, fontweight="bold", pad=12)

        fg = _DARK_FG if self._dark else _LIGHT_FG
        for i, (w, t) in enumerate(zip(weeks, totals)):
            ax.text(i, t + 0.3, str(t), ha="center", fontsize=9, color=fg)

        fig.tight_layout()
        plt.close(fig)
        return fig
