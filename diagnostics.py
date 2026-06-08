"""
diagnostics.py — JARVIS v3 System Diagnostics
Run: python diagnostics.py  or  type "status" / "jarvis status" in chat
"""
from __future__ import annotations
import platform, subprocess, sys
from typing import NamedTuple


class Check(NamedTuple):
    name: str
    ok: bool
    msg: str


def run_all(config=None) -> list[Check]:
    results = []

    # Python
    v = sys.version_info
    results.append(Check("Python", v >= (3, 10),
                          f"{v.major}.{v.minor}.{v.micro}"))

    # Ollama
    try:
        import requests
        from memory.config_manager import get_mark_config as get_config  # noqa
        cfg = config or get_config()
        r = requests.get(f"{cfg.ollama_url}/api/tags", timeout=3)
        if r.ok:
            models = [m["name"] for m in r.json().get("models", [])]
            results.append(Check("Ollama", True,
                f"Online — {', '.join(models[:4]) or 'no models pulled'}"))
        else:
            results.append(Check("Ollama", False, f"HTTP {r.status_code}"))
    except Exception as e:
        results.append(Check("Ollama", False, f"Not reachable: {e}"))

    # Browser CDP
    try:
        import requests
        from memory.config_manager import get_mark_config as get_config  # noqa
        cfg = config or get_config()
        r = requests.get(f"http://localhost:{cfg.cdp_port}/json/version", timeout=2)
        if r.ok:
            results.append(Check("Browser CDP", True,
                r.json().get("Browser", "connected")))
        else:
            raise Exception()
    except Exception:
        results.append(Check("Browser CDP", False,
            "Start Brave with: brave.exe --remote-debugging-port=9222"))

    # Packages
    pkgs = {
        "PySide6":                   "PySide6",
        "requests":                  "requests",
        "PyMuPDF (fitz)":            "fitz",
        "psutil":                    "psutil",
        "mss (screenshot)":          "mss",
        "pyperclip":                 "pyperclip",
        "sentence-transformers":     "sentence_transformers",
        "websockets":                "websockets",
        "PyYAML":                    "yaml",
        "pyttsx3 (TTS)":             "pyttsx3",
        "vosk (wake word)":          "vosk",
        "Pillow":                    "PIL",
    }
    for display, mod in pkgs.items():
        try:
            __import__(mod)
            results.append(Check(display, True, "installed"))
        except ImportError:
            results.append(Check(display, False, "not installed"))

    # GPU
    try:
        r = subprocess.run(
            ["nvidia-smi", "--query-gpu=name", "--format=csv,noheader"],
            capture_output=True, text=True, timeout=5)
        gpu = r.stdout.strip().splitlines()[0] if r.returncode == 0 else None
        results.append(Check("NVIDIA GPU", bool(gpu), gpu or "not found"))
    except Exception:
        results.append(Check("NVIDIA GPU", False, "nvidia-smi not found"))

    return results


def format_report(results: list[Check]) -> str:
    lines = [
        "╔══════════════════════════════════════════╗",
        "║       JARVIS v3 — System Status          ║",
        "╚══════════════════════════════════════════╝",
        f"  Platform: {platform.system()} {platform.release()}",
        "",
    ]
    for r in results:
        icon = "✅" if r.ok else "❌"
        lines.append(f"  {icon}  {r.name:<28}  {r.msg}")
    ok = sum(1 for r in results if r.ok)
    lines += ["", f"  {ok}/{len(results)} checks passed", ""]
    return "\n".join(lines)


if __name__ == "__main__":
    print(format_report(run_all()))
