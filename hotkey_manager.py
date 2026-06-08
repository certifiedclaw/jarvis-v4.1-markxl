"""
hotkey_commands.py — JARVIS v3 Global Hotkey Manager (stub)

Replace this stub with a full implementation using the `keyboard` library
(already in requirements.txt) when you want Ctrl+Alt+J to toggle the window.
"""

from __future__ import annotations
import logging

log = logging.getLogger(__name__)

try:
    import keyboard as _kb
    _HAS_KEYBOARD = True
except ImportError:
    _HAS_KEYBOARD = False
    log.warning("'keyboard' package not installed — hotkeys disabled")


class HotkeyManager:
    DEFAULT_HOTKEY = "ctrl+alt+j"

    def __init__(self, agent=None, window=None, config=None):
        self.agent  = agent
        self.window = window
        self.config = config
        self.hotkey = (config.get("hotkey.toggle", self.DEFAULT_HOTKEY)
                       if config else self.DEFAULT_HOTKEY)
        self._running = False

    def _toggle(self):
        if self.window is None:
            return
        if self.window.isVisible():
            self.window.hide()
        else:
            self.window.show()
            self.window.raise_()
            self.window.activateWindow()

    def start(self):
        if not _HAS_KEYBOARD:
            log.warning("keyboard package missing — hotkey not registered")
            return
        try:
            _kb.add_hotkey(self.hotkey, self._toggle, suppress=False)
            self._running = True
            log.info("Global hotkey registered: %s", self.hotkey)
        except Exception as exc:
            log.warning("Could not register hotkey %s: %s", self.hotkey, exc)

    def stop(self):
        if _HAS_KEYBOARD and self._running:
            try:
                _kb.remove_hotkey(self.hotkey)
            except Exception:
                pass
        self._running = False
        log.info("HotkeyManager stopped")
