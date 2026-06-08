"""
plugin_watcher.py — JARVIS v4.1 Plugin Hot-Reload

Watches the plugins/ directory with watchdog. When a .py file is added,
modified, or deleted while JARVIS is running, it automatically reloads
the plugin loader so the new tool is immediately available — no restart needed.

Usage in main.py / loading_screen.py (after plugins are first loaded):

    from plugin_watcher import start_plugin_watcher
    start_plugin_watcher(plugin_loader, plugin_dir="./plugins")

Requires:  pip install watchdog
"""

from __future__ import annotations

import importlib
import logging
import threading
import time
from pathlib import Path

logger = logging.getLogger(__name__)


def start_plugin_watcher(plugin_loader, plugin_dir: str = "./plugins") -> None:
    """
    Start a background thread that watches plugin_dir for changes and calls
    plugin_loader.reload() when any .py file is added, modified, or removed.

    Parameters
    ----------
    plugin_loader
        The PluginLoader instance from plugins.py.
    plugin_dir
        Path to the plugins directory (default: ./plugins).
    """
    try:
        from watchdog.observers import Observer
        from watchdog.events import FileSystemEventHandler, FileModifiedEvent, \
            FileCreatedEvent, FileDeletedEvent
    except ImportError:
        logger.warning(
            "plugin_watcher: watchdog not installed — hot-reload disabled. "
            "Install with: pip install watchdog"
        )
        return

    plugin_path = Path(plugin_dir).resolve()

    class _PluginHandler(FileSystemEventHandler):
        def __init__(self):
            self._debounce_timer: threading.Timer | None = None
            self._lock = threading.Lock()

        def _schedule_reload(self, event_path: str) -> None:
            if not event_path.endswith(".py"):
                return
            # Debounce: wait 300 ms after the last event before reloading
            with self._lock:
                if self._debounce_timer:
                    self._debounce_timer.cancel()
                self._debounce_timer = threading.Timer(0.3, self._do_reload, args=[event_path])
                self._debounce_timer.daemon = True
                self._debounce_timer.start()

        def _do_reload(self, event_path: str) -> None:
            logger.info("plugin_watcher: change detected in %s — reloading plugins", event_path)
            try:
                plugin_loader.reload()
                tools = plugin_loader.list_tools()
                logger.info("plugin_watcher: reload complete — %d tools available: %s",
                            len(tools), tools)
            except Exception as e:
                logger.error("plugin_watcher: reload failed: %s", e)

        def on_modified(self, event):
            if not event.is_directory:
                self._schedule_reload(event.src_path)

        def on_created(self, event):
            if not event.is_directory:
                self._schedule_reload(event.src_path)

        def on_deleted(self, event):
            if not event.is_directory:
                self._schedule_reload(event.src_path)

    handler = _PluginHandler()
    observer = Observer()
    observer.schedule(handler, str(plugin_path), recursive=False)

    def _run_observer():
        observer.start()
        logger.info("plugin_watcher: watching %s for changes", plugin_path)
        try:
            while observer.is_alive():
                observer.join(timeout=1)
        except Exception:
            pass
        finally:
            observer.stop()
            observer.join()

    t = threading.Thread(target=_run_observer, daemon=True, name="plugin-watcher")
    t.start()
