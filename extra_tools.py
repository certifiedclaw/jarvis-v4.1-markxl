"""
extra_tools.py — JARVIS v3 Extended Capabilities

30+ new tools. All imports are guarded — missing packages produce a
helpful install hint instead of crashing.

Categories:
  Info          — weather, Wikipedia, dictionary, public IP, battery
  Productivity  — notes, reminders, timers, password generator, unit converter
  Files         — zip/unzip, diff, find large files, hash, batch rename, word count
  System        — process list/kill, window list/focus, color picker, auto-type
  Code          — run Python snippet, format JSON, lint check
  Network       — ping, port check, wifi list, speed test (optional)
  Media         — local media (mpv/vlc), volume control (system-level)
"""
from __future__ import annotations
import json
import logging
import os
import platform
import random
import re
import shutil
import string
import subprocess
import threading
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Callable

logger = logging.getLogger(__name__)

# ─────────────────────────────────────────────────────────────────────────────
# INFO
# ─────────────────────────────────────────────────────────────────────────────

def get_weather(city: str = "auto") -> str:
    """Current weather via wttr.in — no API key needed."""
    try:
        import requests
        loc = city if city != "auto" else ""
        url = f"https://wttr.in/{requests.utils.quote(loc)}?format=j1"
        r   = requests.get(url, timeout=8, headers={"User-Agent": "JARVIS/3.0"})
        r.raise_for_status()
        d   = r.json()
        cur = d["current_condition"][0]
        area= d["nearest_area"][0]
        loc_name = (area["areaName"][0]["value"] + ", " +
                    area["country"][0]["value"])
        desc    = cur["weatherDesc"][0]["value"]
        temp_c  = cur["temp_C"]
        temp_f  = cur["temp_F"]
        feels_c = cur["FeelsLikeC"]
        humidity= cur["humidity"]
        wind_kph= cur["windspeedKmph"]
        return (f"📍 {loc_name}\n"
                f"🌤  {desc}\n"
                f"🌡  {temp_c}°C / {temp_f}°F  (feels like {feels_c}°C)\n"
                f"💧 Humidity: {humidity}%\n"
                f"💨 Wind: {wind_kph} km/h")
    except ImportError:
        return "requests not installed"
    except Exception as e:
        return f"Weather error: {e}"


def get_wikipedia(topic: str, sentences: int = 4) -> str:
    """Fetch a Wikipedia summary. No API key needed."""
    try:
        import requests, urllib.parse
        url = ("https://en.wikipedia.org/api/rest_v1/page/summary/"
               + urllib.parse.quote(topic.replace(" ", "_")))
        r = requests.get(url, timeout=8, headers={"User-Agent": "JARVIS/3.0"})
        if r.status_code == 404:
            return f"No Wikipedia article found for: {topic}"
        r.raise_for_status()
        data    = r.json()
        extract = data.get("extract", "")
        # Trim to N sentences
        parts = re.split(r"(?<=[.!?])\s+", extract)
        summary = " ".join(parts[:sentences])
        page_url = data.get("content_urls", {}).get("desktop", {}).get("page", "")
        return f"📖 **{data.get('title','?')}**\n\n{summary}\n\n{page_url}"
    except Exception as e:
        return f"Wikipedia error: {e}"


def get_definition(word: str) -> str:
    """English dictionary definition via Free Dictionary API."""
    try:
        import requests
        r = requests.get(f"https://api.dictionaryapi.dev/api/v2/entries/en/{word}",
                         timeout=6)
        if r.status_code == 404:
            return f"No definition found for: {word}"
        r.raise_for_status()
        data  = r.json()[0]
        title = data.get("word", word)
        lines = [f"📚 **{title}**"]
        for meaning in data.get("meanings", [])[:3]:
            pos  = meaning.get("partOfSpeech", "")
            defs = meaning.get("definitions", [])[:2]
            for d in defs:
                lines.append(f"  *{pos}* — {d['definition']}")
                if d.get("example"):
                    lines.append(f"    e.g. \"{d['example']}\"")
        phonetics = data.get("phonetic", "")
        if phonetics:
            lines.insert(1, f"  {phonetics}")
        return "\n".join(lines)
    except Exception as e:
        return f"Dictionary error: {e}"


def get_public_ip() -> str:
    """Get public IP address and basic geolocation."""
    try:
        import requests
        r = requests.get("https://ipinfo.io/json", timeout=5)
        d = r.json()
        return (f"🌐 IP: {d.get('ip','?')}\n"
                f"   Location: {d.get('city','?')}, {d.get('region','?')}, "
                f"{d.get('country','?')}\n"
                f"   ISP: {d.get('org','?')}")
    except Exception as e:
        return f"IP lookup error: {e}"


def get_battery() -> str:
    """Battery status (laptops only)."""
    try:
        import psutil
        bat = psutil.sensors_battery()
        if bat is None:
            return "No battery detected (desktop or psutil can't read it)."
        plugged = "🔌 Charging" if bat.power_plugged else "🔋 On battery"
        secs    = bat.secsleft
        if secs == psutil.POWER_TIME_UNLIMITED:
            time_str = "fully charged"
        elif secs == psutil.POWER_TIME_UNKNOWN or secs < 0:
            time_str = "unknown time remaining"
        else:
            h, m = divmod(secs // 60, 60)
            time_str = f"{h}h {m}m remaining"
        return f"{plugged}  {bat.percent:.0f}%  ({time_str})"
    except ImportError:
        return "psutil not installed: pip install psutil"
    except Exception as e:
        return f"Battery error: {e}"


# ─────────────────────────────────────────────────────────────────────────────
# PRODUCTIVITY
# ─────────────────────────────────────────────────────────────────────────────

_NOTES_DIR = Path("./data/notes")

def save_note(title: str, content: str) -> str:
    """Save a quick note to data/notes/."""
    try:
        _NOTES_DIR.mkdir(parents=True, exist_ok=True)
        safe = re.sub(r'[^\w\s-]', '', title).strip().replace(" ", "_")
        path = _NOTES_DIR / f"{safe}.md"
        ts   = datetime.now().strftime("%Y-%m-%d %H:%M")
        path.write_text(f"# {title}\n*{ts}*\n\n{content}\n", encoding="utf-8")
        return f"📝 Note saved: {path}"
    except Exception as e:
        return f"Note error: {e}"


def list_notes() -> str:
    """List all saved notes."""
    try:
        _NOTES_DIR.mkdir(parents=True, exist_ok=True)
        notes = sorted(_NOTES_DIR.glob("*.md"))
        if not notes:
            return "No notes yet. Try: save_note(title, content)"
        lines = [f"📒 {n.stem.replace('_',' ')}  ({n.stat().st_size} B)" for n in notes]
        return f"{len(notes)} note(s):\n" + "\n".join(lines)
    except Exception as e:
        return f"Notes error: {e}"


def read_note(title: str) -> str:
    """Read a saved note by title (fuzzy match)."""
    try:
        _NOTES_DIR.mkdir(parents=True, exist_ok=True)
        q = title.lower().replace(" ", "_")
        for f in _NOTES_DIR.glob("*.md"):
            if q in f.stem.lower():
                return f.read_text(encoding="utf-8")
        return f"Note not found: {title}"
    except Exception as e:
        return f"Read note error: {e}"


def delete_note(title: str) -> str:
    """Delete a note by title."""
    try:
        q = title.lower().replace(" ", "_")
        for f in _NOTES_DIR.glob("*.md"):
            if q in f.stem.lower():
                f.unlink()
                return f"Deleted note: {f.stem}"
        return f"Note not found: {title}"
    except Exception as e:
        return f"Delete note error: {e}"


# In-memory reminder store  {id: {time, message, fired}}
_reminders: dict[int, dict] = {}
_reminder_counter = 0
_reminder_notify_cb: Callable | None = None   # set by main_window

def set_reminder_callback(cb: Callable) -> None:
    global _reminder_notify_cb
    _reminder_notify_cb = cb

def remind_me(message: str, minutes: float = 5) -> str:
    """Set a reminder. Fires a desktop notification after N minutes."""
    global _reminder_counter
    _reminder_counter += 1
    rid  = _reminder_counter
    fire_at = datetime.now() + timedelta(minutes=float(minutes))

    def _fire():
        _reminders[rid]["fired"] = True
        _send_notification("⏰ JARVIS Reminder", message)
        if _reminder_notify_cb:
            try:
                _reminder_notify_cb(message)
            except Exception:
                pass

    t = threading.Timer(float(minutes) * 60, _fire)
    t.daemon = True
    t.start()
    _reminders[rid] = {"time": fire_at.isoformat(), "message": message,
                        "fired": False, "timer": t}
    return (f"⏰ Reminder set for {fire_at.strftime('%H:%M:%S')} "
            f"({minutes} min): {message}")


def list_reminders() -> str:
    """List all pending reminders."""
    pending = [(rid, r) for rid, r in _reminders.items() if not r["fired"]]
    if not pending:
        return "No pending reminders."
    lines = [f"  [{rid}] {r['message']}  @ {r['time'][:19]}" for rid, r in pending]
    return f"{len(pending)} reminder(s):\n" + "\n".join(lines)


def cancel_reminder(reminder_id: int) -> str:
    r = _reminders.get(int(reminder_id))
    if not r:
        return f"Reminder #{reminder_id} not found."
    r["timer"].cancel()
    r["fired"] = True
    return f"Cancelled reminder #{reminder_id}: {r['message']}"


def _send_notification(title: str, message: str) -> None:
    try:
        if platform.system() == "Windows":
            subprocess.Popen(
                ["powershell", "-Command",
                 f"Add-Type -AssemblyName System.Windows.Forms; "
                 f"[System.Windows.Forms.MessageBox]::Show('{message}','{title}')"],
                creationflags=0x08000000)
        elif platform.system() == "Darwin":
            subprocess.Popen(
                ["osascript", "-e",
                 f'display notification "{message}" with title "{title}"'])
        else:
            subprocess.Popen(["notify-send", title, message])
    except Exception:
        pass


def set_timer(seconds: int, label: str = "Timer") -> str:
    """Countdown timer with notification."""
    return remind_me(f"⏱ {label} done!", minutes=float(seconds) / 60)


def generate_password(length: int = 16, symbols: bool = True) -> str:
    """Generate a cryptographically random password."""
    import secrets
    chars = string.ascii_letters + string.digits
    if symbols:
        chars += "!@#$%^&*()-_=+[]{}|;:,.<>?"
    pwd = "".join(secrets.choice(chars) for _ in range(int(length)))
    return f"🔑 {pwd}"


def convert_units(value: float, from_unit: str, to_unit: str) -> str:
    """Convert common units. Covers length, weight, temperature, speed, data."""
    # Base units in SI: metres, kg, kelvin, m/s, bytes
    LENGTH = {"mm":0.001,"cm":0.01,"m":1,"km":1000,"in":0.0254,
              "ft":0.3048,"yd":0.9144,"mi":1609.344}
    WEIGHT = {"mg":1e-6,"g":0.001,"kg":1,"lb":0.453592,"oz":0.0283495,"t":1000}
    SPEED  = {"m/s":1,"km/h":1/3.6,"mph":0.44704,"knot":0.514444}
    DATA   = {"b":1,"kb":1024,"mb":1024**2,"gb":1024**3,"tb":1024**4}

    f, t = from_unit.lower().strip(), to_unit.lower().strip()
    v = float(value)

    # Temperature special case
    temp_units = {"c","f","k","celsius","fahrenheit","kelvin"}
    if f in temp_units or t in temp_units:
        # Normalise to Celsius first
        if f in ("f","fahrenheit"):   c = (v - 32) * 5/9
        elif f in ("k","kelvin"):     c = v - 273.15
        else:                          c = v
        if t in ("f","fahrenheit"):   result = c * 9/5 + 32
        elif t in ("k","kelvin"):     result = c + 273.15
        else:                          result = c
        return f"{value} {from_unit} = {result:.4g} {to_unit}"

    for table in (LENGTH, WEIGHT, SPEED, DATA):
        if f in table and t in table:
            result = v * table[f] / table[t]
            return f"{value} {from_unit} = {result:.6g} {to_unit}"

    return (f"Unknown unit pair: {from_unit} → {to_unit}\n"
            "Supported: length (mm/cm/m/km/in/ft/yd/mi), "
            "weight (mg/g/kg/lb/oz/t), temperature (C/F/K), "
            "speed (m/s/km/h/mph/knot), data (b/kb/mb/gb/tb)")


# ─────────────────────────────────────────────────────────────────────────────
# FILES
# ─────────────────────────────────────────────────────────────────────────────

def zip_files(paths: list | str, output: str = "") -> str:
    """Zip one or more files/folders."""
    try:
        import zipfile
        if isinstance(paths, str):
            paths = [p.strip() for p in paths.split(",") if p.strip()]
        if not output:
            output = paths[0].rstrip("/\\") + ".zip"
        output = os.path.expanduser(output)
        with zipfile.ZipFile(output, "w", zipfile.ZIP_DEFLATED) as zf:
            for p in paths:
                p = os.path.expanduser(p.strip())
                if os.path.isdir(p):
                    for root, _, files in os.walk(p):
                        for f in files:
                            fp = os.path.join(root, f)
                            zf.write(fp, os.path.relpath(fp, os.path.dirname(p)))
                else:
                    zf.write(p, os.path.basename(p))
        size = Path(output).stat().st_size
        return f"📦 Created {output}  ({size:,} bytes)"
    except Exception as e:
        return f"Zip error: {e}"


def unzip_file(path: str, dest: str = "") -> str:
    """Extract a zip file."""
    try:
        import zipfile
        path = os.path.expanduser(path)
        dest = os.path.expanduser(dest) if dest else str(Path(path).parent)
        with zipfile.ZipFile(path, "r") as zf:
            zf.extractall(dest)
            names = zf.namelist()
        return f"📂 Extracted {len(names)} file(s) to {dest}"
    except Exception as e:
        return f"Unzip error: {e}"


def hash_file(path: str, algorithm: str = "sha256") -> str:
    """Calculate file hash (md5, sha1, sha256, sha512)."""
    import hashlib
    path = os.path.expanduser(path)
    try:
        h = hashlib.new(algorithm)
        with open(path, "rb") as f:
            for chunk in iter(lambda: f.read(65536), b""):
                h.update(chunk)
        return f"{algorithm.upper()}: {h.hexdigest()}\nFile: {path}"
    except Exception as e:
        return f"Hash error: {e}"


def diff_files(file1: str, file2: str) -> str:
    """Show line-by-line diff of two text files."""
    try:
        import difflib
        a = Path(os.path.expanduser(file1)).read_text(encoding="utf-8", errors="replace").splitlines()
        b = Path(os.path.expanduser(file2)).read_text(encoding="utf-8", errors="replace").splitlines()
        diff = list(difflib.unified_diff(a, b,
                    fromfile=file1, tofile=file2, lineterm=""))
        if not diff:
            return "Files are identical."
        return "\n".join(diff[:100]) + (f"\n… ({len(diff)-100} more lines)" if len(diff) > 100 else "")
    except Exception as e:
        return f"Diff error: {e}"


def find_large_files(root: str = "~", min_mb: float = 100) -> str:
    """Find files larger than min_mb megabytes."""
    root = os.path.expanduser(root)
    min_bytes = float(min_mb) * 1_048_576
    try:
        found = []
        for dp, _, fnames in os.walk(root):
            if any(p.startswith(".") for p in Path(dp).parts[-2:]):
                continue
            for fname in fnames:
                fp = os.path.join(dp, fname)
                try:
                    sz = os.path.getsize(fp)
                    if sz >= min_bytes:
                        found.append((sz, fp))
                except OSError:
                    pass
        if not found:
            return f"No files >{min_mb} MB found in {root}"
        found.sort(reverse=True)
        lines = [f"  {sz/1_048_576:.1f} MB  {p}" for sz, p in found[:30]]
        return f"Files >{min_mb} MB in {root}:\n" + "\n".join(lines)
    except Exception as e:
        return f"Find error: {e}"


def word_count(text_or_path: str) -> str:
    """Count words, lines, and characters in text or a file."""
    try:
        p = Path(os.path.expanduser(text_or_path))
        if p.exists() and p.is_file():
            text = p.read_text(encoding="utf-8", errors="replace")
            source = p.name
        else:
            text   = text_or_path
            source = "text"
        words = len(text.split())
        lines = text.count("\n") + 1
        chars = len(text)
        return f"{source}: {words:,} words  {lines:,} lines  {chars:,} chars"
    except Exception as e:
        return f"Word count error: {e}"


def batch_rename(folder: str, pattern: str, replacement: str,
                 extension: str = "") -> str:
    """
    Rename files in a folder using find/replace on filenames.
    Example: batch_rename("~/Downloads", "IMG_", "photo_", ".jpg")
    """
    try:
        folder = os.path.expanduser(folder)
        renamed = 0
        for fname in os.listdir(folder):
            if extension and not fname.lower().endswith(extension.lower()):
                continue
            if pattern in fname:
                new_name = fname.replace(pattern, replacement)
                os.rename(os.path.join(folder, fname),
                          os.path.join(folder, new_name))
                renamed += 1
        return f"Renamed {renamed} file(s) in {folder}"
    except Exception as e:
        return f"Rename error: {e}"


# ─────────────────────────────────────────────────────────────────────────────
# SYSTEM — processes, windows, input
# ─────────────────────────────────────────────────────────────────────────────

def list_processes(filter_name: str = "", top: int = 20) -> str:
    """List running processes sorted by CPU usage."""
    try:
        import psutil
        procs = []
        for p in psutil.process_iter(["pid", "name", "cpu_percent", "memory_info"]):
            try:
                info = p.info
                if filter_name and filter_name.lower() not in info["name"].lower():
                    continue
                mem_mb = (info["memory_info"].rss / 1_048_576) if info["memory_info"] else 0
                procs.append((info["cpu_percent"], info["pid"], info["name"], mem_mb))
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                pass
        procs.sort(reverse=True)
        lines = [f"  PID {pid:6}  {cpu:5.1f}% CPU  {mem:6.1f} MB  {name}"
                 for cpu, pid, name, mem in procs[:top]]
        return f"{'Filtered' if filter_name else 'Top'} processes:\n" + "\n".join(lines)
    except ImportError:
        return "psutil not installed: pip install psutil"
    except Exception as e:
        return f"Process list error: {e}"


def kill_process(name_or_pid: str) -> str:
    """Kill a process by name or PID. Requires confirmation (handled by safety layer)."""
    try:
        import psutil
        target = str(name_or_pid).strip()
        killed = []
        for p in psutil.process_iter(["pid", "name"]):
            try:
                if target.isdigit() and p.pid == int(target):
                    p.terminate(); killed.append(f"{p.name()} ({p.pid})")
                elif not target.isdigit() and target.lower() in p.name().lower():
                    p.terminate(); killed.append(f"{p.name()} ({p.pid})")
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                pass
        return f"Terminated: {', '.join(killed)}" if killed else f"No process found: {target}"
    except ImportError:
        return "psutil not installed"
    except Exception as e:
        return f"Kill error: {e}"


def list_windows() -> str:
    """List visible application windows (Windows only)."""
    if platform.system() != "Windows":
        return "Window listing is Windows-only."
    try:
        import ctypes
        import ctypes.wintypes as wintypes
        result = []
        def enum_cb(hwnd, _):
            if ctypes.windll.user32.IsWindowVisible(hwnd):
                buf = ctypes.create_unicode_buffer(256)
                ctypes.windll.user32.GetWindowTextW(hwnd, buf, 256)
                title = buf.value.strip()
                if title:
                    result.append(f"  HWND {hwnd:8x}  {title}")
            return True
        WNDENUMPROC = ctypes.WINFUNCTYPE(ctypes.c_bool, wintypes.HWND, wintypes.LPARAM)
        ctypes.windll.user32.EnumWindows(WNDENUMPROC(enum_cb), 0)
        return f"{len(result)} window(s):\n" + "\n".join(result[:40])
    except Exception as e:
        return f"Window list error: {e}"


def focus_window(title: str) -> str:
    """Bring a window to the foreground by partial title match (Windows only)."""
    if platform.system() != "Windows":
        return "Window focus is Windows-only."
    try:
        import ctypes, ctypes.wintypes as wt
        found = []
        def cb(hwnd, _):
            buf = ctypes.create_unicode_buffer(256)
            ctypes.windll.user32.GetWindowTextW(hwnd, buf, 256)
            if title.lower() in buf.value.lower():
                found.append(hwnd)
            return True
        WNDENUMPROC = ctypes.WINFUNCTYPE(ctypes.c_bool, wt.HWND, wt.LPARAM)
        ctypes.windll.user32.EnumWindows(WNDENUMPROC(cb), 0)
        if not found:
            return f"No window matching: {title}"
        hwnd = found[0]
        ctypes.windll.user32.ShowWindow(hwnd, 9)   # SW_RESTORE
        ctypes.windll.user32.SetForegroundWindow(hwnd)
        return f"Focused window: {title}"
    except Exception as e:
        return f"Focus error: {e}"


def type_text(text: str) -> str:
    """Type text into the currently focused window."""
    try:
        import keyboard
        keyboard.write(text, delay=0.02)
        return f"Typed {len(text)} characters."
    except ImportError:
        return "keyboard not installed: pip install keyboard"
    except Exception as e:
        return f"Type error: {e}"


def get_mouse_color() -> str:
    """Get the hex color of the pixel under the mouse cursor."""
    try:
        import pyautogui
        from PIL import ImageGrab
        x, y = pyautogui.position()
        img  = ImageGrab.grab(bbox=(x, y, x+1, y+1))
        r, g, b = img.getpixel((0, 0))[:3]
        return f"🎨 #{r:02X}{g:02X}{b:02X}  (R:{r} G:{g} B:{b})  at ({x},{y})"
    except ImportError:
        return "pyautogui / Pillow not installed"
    except Exception as e:
        return f"Color pick error: {e}"


def set_system_volume(level: int) -> str:
    """Set system master volume 0-100 (Windows only)."""
    if platform.system() != "Windows":
        return "System volume control is Windows-only."
    try:
        from ctypes import cast, POINTER
        from comtypes import CLSCTX_ALL
        from pycaw.pycaw import AudioUtilities, IAudioEndpointVolume
        devices = AudioUtilities.GetSpeakers()
        interface = devices.Activate(IAudioEndpointVolume._iid_, CLSCTX_ALL, None)
        volume = cast(interface, POINTER(IAudioEndpointVolume))
        scalar = max(0.0, min(1.0, int(level) / 100.0))
        volume.SetMasterVolumeLevelScalar(scalar, None)
        return f"🔊 System volume set to {level}%"
    except ImportError:
        return "pycaw not installed: pip install pycaw comtypes"
    except Exception as e:
        return f"Volume error: {e}"


# ─────────────────────────────────────────────────────────────────────────────
# CODE
# ─────────────────────────────────────────────────────────────────────────────

def run_python(code: str, timeout: int = 10) -> str:
    """
    Execute a Python code snippet in a subprocess sandbox.
    stdout/stderr are captured and returned.
    """
    try:
        result = subprocess.run(
            ["python", "-c", code],
            capture_output=True, text=True, timeout=int(timeout))
        out = result.stdout[:2000]
        err = result.stderr[:500]
        if err and not out:
            return f"[stderr]\n{err}"
        if err:
            out += f"\n[stderr]\n{err}"
        return out or "(no output)"
    except subprocess.TimeoutExpired:
        return f"Timed out after {timeout}s"
    except Exception as e:
        return f"Run error: {e}"


def calculate(expression: str) -> str:
    """
    Safely evaluate a math expression.
    Supports: +−×/ ** sqrt sin cos log abs round etc.
    """
    import math
    safe_globals = {k: getattr(math, k) for k in dir(math) if not k.startswith("_")}
    safe_globals["abs"] = abs
    safe_globals["round"] = round
    # Normalise ×÷ symbols
    expr = expression.replace("×", "*").replace("÷", "/").replace("^", "**")
    # Strip anything that's not a safe character
    if re.search(r"[^\d\s\+\-\*\/\.\(\)\,\_a-zA-Z]", expr):
        return f"Unsafe expression: {expression}"
    try:
        result = eval(expr, {"__builtins__": {}}, safe_globals)  # noqa: S307
        return f"= {result}"
    except Exception as e:
        return f"Calculation error: {e}"


def format_json(text: str) -> str:
    """Pretty-print a JSON string."""
    try:
        parsed = json.loads(text)
        return json.dumps(parsed, indent=2, ensure_ascii=False)
    except json.JSONDecodeError as e:
        return f"Invalid JSON: {e}"


def lint_python(path: str) -> str:
    """Run pyflakes on a Python file for quick error checking."""
    path = os.path.expanduser(path)
    try:
        result = subprocess.run(["python", "-m", "pyflakes", path],
                                capture_output=True, text=True, timeout=15)
        out = (result.stdout + result.stderr).strip()
        return out or f"✅ No issues found in {path}"
    except Exception as e:
        return f"Lint error: {e}"


# ─────────────────────────────────────────────────────────────────────────────
# NETWORK
# ─────────────────────────────────────────────────────────────────────────────

def ping_host(host: str, count: int = 4) -> str:
    """Ping a hostname or IP address."""
    try:
        flag = "-n" if platform.system() == "Windows" else "-c"
        result = subprocess.run(
            ["ping", flag, str(count), host],
            capture_output=True, text=True, timeout=15)
        lines = (result.stdout + result.stderr).strip().splitlines()
        # Return last few lines (summary)
        return "\n".join(lines[-6:]) if lines else "No response"
    except subprocess.TimeoutExpired:
        return f"{host}: timed out"
    except Exception as e:
        return f"Ping error: {e}"


def check_port(host: str, port: int) -> str:
    """Check if a TCP port is open."""
    import socket
    try:
        sock = socket.create_connection((host, int(port)), timeout=3)
        sock.close()
        return f"✅ {host}:{port} is OPEN"
    except (socket.timeout, ConnectionRefusedError):
        return f"❌ {host}:{port} is CLOSED / unreachable"
    except Exception as e:
        return f"Port check error: {e}"


def list_wifi_networks() -> str:
    """List available WiFi networks (Windows/Linux)."""
    try:
        if platform.system() == "Windows":
            result = subprocess.run(
                ["netsh", "wlan", "show", "networks"],
                capture_output=True, text=True, timeout=10)
            lines = [l for l in result.stdout.splitlines()
                     if "SSID" in l or "Signal" in l or "Authentication" in l]
            return "\n".join(lines) if lines else "No networks found."
        elif platform.system() == "Linux":
            result = subprocess.run(
                ["nmcli", "-f", "SSID,SIGNAL,SECURITY", "dev", "wifi"],
                capture_output=True, text=True, timeout=10)
            return result.stdout or "nmcli not available"
        else:
            return "WiFi list not supported on this platform."
    except Exception as e:
        return f"WiFi error: {e}"


def get_local_ip() -> str:
    """Get local network IP address."""
    import socket
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return f"Local IP: {ip}"
    except Exception as e:
        return f"IP error: {e}"


# ─────────────────────────────────────────────────────────────────────────────
# MEDIA — local files
# ─────────────────────────────────────────────────────────────────────────────

def play_file(path: str) -> str:
    """Open a media file with the system default player."""
    path = os.path.expanduser(path)
    if not Path(path).exists():
        return f"File not found: {path}"
    try:
        if platform.system() == "Windows":
            os.startfile(path)
        elif platform.system() == "Darwin":
            subprocess.Popen(["open", path])
        else:
            subprocess.Popen(["xdg-open", path])
        return f"▶ Opening: {Path(path).name}"
    except Exception as e:
        return f"Play error: {e}"


# ─────────────────────────────────────────────────────────────────────────────
# MISC
# ─────────────────────────────────────────────────────────────────────────────

def generate_qr(text: str, save_path: str = "") -> str:
    """Generate a QR code image. Requires: pip install qrcode Pillow"""
    try:
        import qrcode
        img = qrcode.make(text)
        if not save_path:
            save_path = str(Path("./data") / f"qr_{int(time.time())}.png")
        Path(save_path).parent.mkdir(parents=True, exist_ok=True)
        img.save(save_path)
        return f"QR code saved: {save_path}"
    except ImportError:
        return "qrcode not installed: pip install qrcode Pillow"
    except Exception as e:
        return f"QR error: {e}"


def get_current_datetime(timezone: str = "") -> str:
    """Get the current date and time."""
    try:
        if timezone:
            try:
                from zoneinfo import ZoneInfo
                now = datetime.now(ZoneInfo(timezone))
                return now.strftime(f"%A, %B %d %Y  %H:%M:%S  ({timezone})")
            except Exception:
                pass
        now = datetime.now()
        return now.strftime("%A, %B %d %Y  %H:%M:%S")
    except Exception as e:
        return f"DateTime error: {e}"


def screenshot_region(x: int, y: int, width: int, height: int,
                      save_path: str = "") -> str:
    """Capture a specific region of the screen."""
    try:
        import mss, mss.tools
        if not save_path:
            save_path = str(Path("./data/screenshots") /
                           f"region_{int(time.time())}.png")
        Path(save_path).parent.mkdir(parents=True, exist_ok=True)
        with mss.mss() as sct:
            monitor = {"top": int(y), "left": int(x),
                       "width": int(width), "height": int(height)}
            img = sct.grab(monitor)
            mss.tools.to_png(img.rgb, img.size, output=save_path)
        return save_path
    except ImportError:
        return "mss not installed: pip install mss"
    except Exception as e:
        return f"Region screenshot error: {e}"


def translate_text(text: str, target_lang: str = "es") -> str:
    """
    Translate text using LibreTranslate (free, self-hostable) or
    falls back to asking the LLM.
    Returns translation or a fallback message.
    """
    try:
        import requests
        # Try public LibreTranslate instance
        r = requests.post(
            "https://libretranslate.de/translate",
            json={"q": text, "source": "auto", "target": target_lang},
            timeout=8, headers={"Content-Type": "application/json"})
        if r.ok:
            result = r.json().get("translatedText", "")
            if result:
                return f"[{target_lang.upper()}] {result}"
        raise Exception("LibreTranslate unavailable")
    except Exception:
        # Fallback hint for agent to use LLM
        return (f"TRANSLATE_VIA_LLM:{target_lang}:{text}"
                "  (LibreTranslate not reachable — ask the LLM directly)")


def random_fact() -> str:
    """Get a random interesting fact from an API."""
    try:
        import requests
        r = requests.get("https://uselessfacts.jsph.pl/random.json?language=en",
                         timeout=6, headers={"User-Agent": "JARVIS/3.0"})
        return f"💡 {r.json().get('text','No fact returned')}"
    except Exception as e:
        return f"Fact error: {e}"
