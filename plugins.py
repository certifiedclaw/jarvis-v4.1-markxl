"""
plugins.py — JARVIS v3 Plugin System
Drop .py files into plugins/ directory. Each must define:
  PLUGIN_NAME = "name"
  PLUGIN_TOOLS = {"tool_name": callable}
"""
from __future__ import annotations
import importlib.util, logging
from pathlib import Path
from typing import Callable

logger = logging.getLogger(__name__)


class PluginSystem:
    def __init__(self, config=None) -> None:
        from memory.config_manager import get_mark_config as get_config
        cfg = config or get_config()
        self._plugin_dir = Path(cfg.get("plugins.plugin_dir", "./plugins"))
        self._config = cfg
        self._plugins: dict = {}
        self._tools: dict[str, Callable] = {}

    def load_all(self) -> int:
        self._plugin_dir.mkdir(parents=True, exist_ok=True)
        count = 0
        for f in sorted(self._plugin_dir.glob("*.py")):
            if not f.name.startswith("_") and self._load(f):
                count += 1
        logger.info("Loaded %d plugin(s)", count)
        return count

    def _load(self, path: Path) -> bool:
        try:
            spec = importlib.util.spec_from_file_location(path.stem, path)
            mod  = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(mod)
            name  = getattr(mod, "PLUGIN_NAME", path.stem)
            tools = getattr(mod, "PLUGIN_TOOLS", {})
            if hasattr(mod, "on_load"):
                mod.on_load(self._config)
            self._plugins[name] = mod
            for tname, fn in tools.items():
                self._tools[f"{name}.{tname}"] = fn
                self._tools.setdefault(tname, fn)
            logger.info("Plugin: %s  (%d tools)", name, len(tools))
            return True
        except Exception as e:
            logger.warning("Plugin load failed %s: %s", path.name, e)
            return False

    def list_tools(self) -> list[str]:
        return list(self._tools.keys())

    def execute_tool(self, name: str, **kwargs) -> str:
        fn = self._tools.get(name)
        if fn is None:
            return f"Plugin tool not found: {name}"
        try:
            return str(fn(**kwargs) or "Done.")
        except Exception as e:
            return f"Plugin '{name}' error: {e}"

    def unload_all(self) -> None:
        for mod in self._plugins.values():
            if hasattr(mod, "on_unload"):
                try:
                    mod.on_unload()
                except Exception:
                    pass
        self._plugins.clear()
        self._tools.clear()
