from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT: Path = Path(__file__).resolve().parent

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


def _ensure_directories() -> None:
    for directory in ("database", "exports", "logs", "assets/icons", "assets/themes"):
        (PROJECT_ROOT / directory).mkdir(parents=True, exist_ok=True)


def main() -> None:
    _ensure_directories()

    from settings import Settings
    cfg = Settings()

    from logger import setup_logging
    log = setup_logging()
    log.info("=" * 60)
    log.info(f"  {cfg.app_name} v{cfg.app_version} starting ...")
    log.info("=" * 60)

    if "--reset" in sys.argv:
        cfg.reset_to_defaults()
        log.info("Settings reset to factory defaults.")
        print("[OK] Settings reset to factory defaults.")
        return

    try:
        from gui import launch
        launch(cfg)
    except Exception as exc:
        log.critical(f"Fatal error during GUI launch: {exc}", exc_info=True)
        raise


if __name__ == "__main__":
    main()
