import json
import sys
from pathlib import Path


def get_base_dir() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).parent
    return Path(__file__).resolve().parent.parent


BASE_DIR    = get_base_dir()
CONFIG_DIR  = BASE_DIR / "config"
CONFIG_FILE = CONFIG_DIR / "api_keys.json"


def ensure_config_dir() -> None:
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)


def config_exists() -> bool:
    return CONFIG_FILE.exists()


def save_config(cfg: dict) -> None:
    ensure_config_dir()
    existing: dict = {}
    if CONFIG_FILE.exists():
        try:
            existing = json.loads(CONFIG_FILE.read_text(encoding="utf-8"))
        except Exception:
            existing = {}
    existing.update(cfg)
    CONFIG_FILE.write_text(json.dumps(existing, indent=2), encoding="utf-8")


def load_api_keys() -> dict:
    if not CONFIG_FILE.exists():
        return {}
    try:
        return json.loads(CONFIG_FILE.read_text(encoding="utf-8"))
    except Exception as e:
        print(f"❌ Failed to load api_keys.json: {e}")
        return {}


class _MarkConfigAdapter:
    """
    Thin adapter so JARVIS-borrowed modules (semantic_memory, rag, plugins, etc.)
    can call config.get("dotted.key", default) and config.property_name
    against Mark-XL's JSON config without needing JARVIS's config.py.
    """
    _DEFAULTS = {
        "memory.db_path":              "./data/memory.db",
        "memory.relevance_threshold":  0.35,
        "memory.chat_history_limit":   100,
        "memory.embedding_model":      "all-MiniLM-L6-v2",
        "memory.window":               12,
        "rag.index_path":              "./data/rag_index",
        "rag.chunk_size":              500,
        "rag.chunk_overlap":           50,
        "rag.top_k":                   5,
        "plugins.plugin_dir":          "./plugins",
        "hotkey.toggle":               "ctrl+alt+j",
        "safety.allowed_paths":        ["~", "."],
        "safety.confirm_on":           ["delete", "shell", "write_file"],
        "llm.ollama_url":              "http://localhost:11434",
        "llm.fast_model":              "qwen2.5:7b",
        "llm.deep_model":              "qwen2.5:7b",
        "llm.vision_model":            "llava:latest",
        "llm.auto_route":              False,
        "llm.route_threshold":         400,
        "llm.temperature":             0.4,
        "llm.num_ctx":                 8192,
        "llm.timeout_seconds":         120,
        "logging.log_dir":             "./logs",
        "browser.cdp_port":            9222,
        "mcp.enabled":                 False,
        "mcp.servers":                 [],
        "osint.max_output_chars":      2000,
        "osint.timeout_seconds":       30,
    }

    def __init__(self):
        self._raw = load_api_keys()

    def get(self, key: str, default=None):
        # Check raw JSON first (top-level keys)
        top = key.split(".")[0]
        if top in self._raw:
            # For nested keys, just return the top-level value if flat key matches
            if "." not in key:
                return self._raw.get(key, default)
        # Fall back to defaults table
        val = self._DEFAULTS.get(key, default)
        return val

    # ── Properties expected by router.py / diagnostics.py ────────────────
    @property
    def ollama_url(self):
        return self._raw.get("llm_url", self._DEFAULTS["llm.ollama_url"])

    @property
    def fast_model(self):
        return self._raw.get("llm_model", self._DEFAULTS["llm.fast_model"])

    @property
    def deep_model(self):
        return self._raw.get("llm_model", self._DEFAULTS["llm.deep_model"])

    @property
    def vision_model(self):
        return self._DEFAULTS["llm.vision_model"]

    @property
    def cdp_port(self):
        return int(self._DEFAULTS["browser.cdp_port"])

    @property
    def allowed_paths(self):
        import os
        return [os.path.expanduser(p) for p in self._DEFAULTS["safety.allowed_paths"]]

    @property
    def confirm_on(self):
        return self._DEFAULTS["safety.confirm_on"]


_mark_config_instance = None


def get_mark_config() -> _MarkConfigAdapter:
    global _mark_config_instance
    if _mark_config_instance is None:
        _mark_config_instance = _MarkConfigAdapter()
    return _mark_config_instance


def is_configured() -> bool:
    cfg = load_api_keys()
    return (
        bool(cfg.get("os_system")) and
        bool(cfg.get("llm_model")) and
        bool(cfg.get("stt_engine")) and
        bool(cfg.get("tts_engine"))
    )
