from __future__ import annotations

import threading
from datetime import datetime
from typing import Callable, Optional

import schedule

from logger import get_logger
from settings import Settings

log = get_logger(__name__)


class ScrapeScheduler:
    def __init__(self, scrape_fn: Callable[[], None], on_tick: Optional[Callable[[str], None]] = None) -> None:
        self._scrape_fn = scrape_fn
        self._on_tick = on_tick or (lambda msg: None)
        self._cfg = Settings()

        self._thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()
        self._running = False
        self._interval: int = self._cfg.scheduler_interval
        self._scheduler = schedule.Scheduler()

    @property
    def is_running(self) -> bool:
        return self._running and self._thread is not None and self._thread.is_alive()

    @property
    def interval_minutes(self) -> int:
        return self._interval

    def start(self, interval_minutes: Optional[int] = None) -> None:
        if self.is_running:
            log.warning("Scheduler already running.")
            return

        if interval_minutes is not None:
            self._interval = interval_minutes
            self._cfg.scheduler_interval = interval_minutes

        self._stop_event.clear()
        self._scheduler.clear()
        self._scheduler.every(self._interval).minutes.do(self._job)

        self._thread = threading.Thread(target=self._loop, name="ScrapeScheduler", daemon=True)
        self._running = True
        self._thread.start()

        msg = f"Scheduler started: every {self._interval} min"
        log.info(msg)
        self._on_tick(msg)

    def stop(self) -> None:
        if not self._running:
            return

        self._stop_event.set()
        self._running = False
        self._scheduler.clear()

        msg = "Scheduler stopped."
        log.info(msg)
        self._on_tick(msg)

    def restart(self, interval_minutes: Optional[int] = None) -> None:
        self.stop()
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=2)
        self.start(interval_minutes)

    def every_15_minutes(self) -> None:
        self.restart(interval_minutes=15)

    def every_30_minutes(self) -> None:
        self.restart(interval_minutes=30)

    def every_hour(self) -> None:
        self.restart(interval_minutes=60)

    def _loop(self) -> None:
        log.debug("Scheduler loop started.")
        while not self._stop_event.is_set():
            self._scheduler.run_pending()
            self._stop_event.wait(timeout=1.0)
        log.debug("Scheduler loop exited.")

    def _job(self) -> None:
        now = datetime.now().strftime("%H:%M:%S")
        msg = f"[{now}] Scheduled scrape starting ..."
        log.info(msg)
        self._on_tick(msg)

        try:
            self._scrape_fn()
            done_msg = f"[{now}] Scheduled scrape completed."
            log.info(done_msg)
            self._on_tick(done_msg)
        except Exception as exc:
            err_msg = f"[{now}] Scheduled scrape failed: {exc}"
            log.error(err_msg, exc_info=True)
            self._on_tick(err_msg)
