"""
core/file_watcher.py — MARK XL File Watcher
Auto-indexes new files dropped into watched directories into the RAG engine.
Inspired by OpenJarvis connectors/sync_engine.py pattern.

Usage:
    from core.file_watcher import FileWatcher
    watcher = FileWatcher(rag_engine, watched_dirs=["~/Documents", "~/Obsidian"])
    watcher.start()   # non-blocking, runs in background thread
    watcher.stop()
"""
from __future__ import annotations
import logging
import os
import threading
import time
from pathlib import Path

logger = logging.getLogger(__name__)

_SUPPORTED = {".pdf", ".md", ".txt", ".rst", ".csv", ".docx"}


class FileWatcher:
    """
    Watches directories for new/modified files and auto-indexes them into RAG.
    Uses polling (no watchdog dependency) for maximum compatibility.
    """

    def __init__(
        self,
        rag_engine,
        watched_dirs: list[str] | None = None,
        poll_interval: float = 5.0,
        notify_cb=None,
    ) -> None:
        self._rag = rag_engine
        self._dirs = [Path(os.path.expanduser(d)) for d in (watched_dirs or [])]
        self._interval = poll_interval
        self._notify_cb = notify_cb  # optional: fn(str) to show a log message
        self._seen: dict[str, float] = {}   # path → mtime
        self._running = False
        self._thread: threading.Thread | None = None

    def start(self) -> None:
        if not self._dirs:
            logger.debug("FileWatcher: no directories configured, not starting")
            return
        self._running = True
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()
        logger.info("FileWatcher started — watching %d dir(s)", len(self._dirs))

    def stop(self) -> None:
        self._running = False

    def add_directory(self, path: str) -> None:
        p = Path(os.path.expanduser(path))
        if p not in self._dirs:
            self._dirs.append(p)
            logger.info("FileWatcher: added %s", p)

    def _run(self) -> None:
        while self._running:
            try:
                self._scan()
            except Exception as e:
                logger.debug("FileWatcher scan error: %s", e)
            time.sleep(self._interval)

    def _scan(self) -> None:
        for watch_dir in self._dirs:
            if not watch_dir.exists():
                continue
            for root, _, files in os.walk(watch_dir):
                for fname in files:
                    fpath = Path(root) / fname
                    if fpath.suffix.lower() not in _SUPPORTED:
                        continue
                    try:
                        mtime = fpath.stat().st_mtime
                        key   = str(fpath)
                        if key not in self._seen or self._seen[key] < mtime:
                            self._seen[key] = mtime
                            if key in self._seen:
                                # File was modified (not first scan)
                                self._index(fpath)
                            else:
                                # First scan — just record, don't index everything
                                pass
                    except OSError:
                        pass

    def _index(self, path: Path) -> None:
        if self._rag is None:
            return
        try:
            result = self._rag.index_file(str(path))
            msg = f"FileWatcher: auto-indexed {path.name} → {result}"
            logger.info(msg)
            if self._notify_cb:
                self._notify_cb(msg)
        except Exception as e:
            logger.debug("FileWatcher index error for %s: %s", path.name, e)


def start_file_watcher(rag_engine, config=None, notify_cb=None) -> FileWatcher | None:
    """
    Convenience: create and start a FileWatcher from config.
    Returns the watcher instance (or None if no dirs configured).
    """
    watch_dirs: list[str] = []
    if config:
        try:
            watch_dirs = config.get("rag.watch_dirs", []) or []
        except Exception:
            pass

    if not watch_dirs:
        return None

    watcher = FileWatcher(rag_engine, watched_dirs=watch_dirs, notify_cb=notify_cb)
    watcher.start()
    return watcher
