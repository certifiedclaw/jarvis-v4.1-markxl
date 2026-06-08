"""
memory_engine.py — JARVIS v3 Memory Engine
SQLite-backed episodic memory + in-session working memory.
Encoder is LAZY — loads on first query, never blocks startup.
"""
from __future__ import annotations
import logging, sqlite3, time
from pathlib import Path
from typing import NamedTuple

logger = logging.getLogger(__name__)


class MemoryEntry(NamedTuple):
    id: int
    role: str
    content: str
    timestamp: float


class MemoryEngine:
    def __init__(self, config=None) -> None:
        from memory.config_manager import get_mark_config as get_config
        cfg = config or get_config()
        self._db_path = Path(cfg.get("memory.db_path", "./data/memory.db"))
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        self._threshold     = float(cfg.get("memory.relevance_threshold", 0.35))
        self._history_limit = int(cfg.get("memory.chat_history_limit", 100))
        self._embedding_model = cfg.get("memory.embedding_model", "all-MiniLM-L6-v2")

        self._conn = self._connect()
        self._session: list[dict] = []

        # Encoder is intentionally NOT loaded here — loading SentenceTransformer
        # can take 5-30 seconds on first run and blocks the loading screen.
        # It is loaded lazily on first memory query instead.
        self._encoder = None
        self._encoder_tried = False

    # ── DB setup ──────────────────────────────────────────────────────────────
    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(str(self._db_path), check_same_thread=False)
        conn.execute("""CREATE TABLE IF NOT EXISTS memories (
            id        INTEGER PRIMARY KEY AUTOINCREMENT,
            role      TEXT    NOT NULL DEFAULT 'exchange',
            content   TEXT    NOT NULL,
            timestamp REAL    NOT NULL,
            embedding BLOB
        )""")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_ts ON memories(timestamp DESC)")
        conn.commit()
        return conn

    # ── Lazy encoder ──────────────────────────────────────────────────────────
    def _ensure_encoder(self) -> None:
        """Load sentence-transformers only on first use, not at startup."""
        if self._encoder_tried:
            return
        self._encoder_tried = True
        try:
            from sentence_transformers import SentenceTransformer
            self._encoder = SentenceTransformer(self._embedding_model)
            logger.info("Semantic memory enabled (%s)", self._embedding_model)
        except ImportError:
            logger.info("sentence-transformers not installed — recency-only memory")
        except Exception as e:
            logger.warning("Encoder load failed: %s", e)

    # ── Write ──────────────────────────────────────────────────────────────────
    def store(self, user_input: str, response: str) -> None:
        ts  = time.time()
        combined = f"User: {user_input}\nAssistant: {response}"
        self._conn.execute(
            "INSERT INTO memories(role,content,timestamp,embedding) VALUES(?,?,?,?)",
            ("exchange", combined, ts, self._encode(combined)))
        self._conn.commit()
        self._session.append({"role": "user",      "content": user_input})
        self._session.append({"role": "assistant",  "content": response})
        if len(self._session) > self._history_limit:
            self._session = self._session[-self._history_limit:]

    def add_message(self, role: str, content: str) -> None:
        self._session.append({"role": role, "content": content})
        if len(self._session) > self._history_limit:
            self._session = self._session[-self._history_limit:]

    # ── Read ───────────────────────────────────────────────────────────────────
    def get_session(self) -> list[dict]:
        return list(self._session)

    def clear_session(self) -> None:
        self._session.clear()

    def get_recent(self, n: int = 10) -> list[MemoryEntry]:
        cur = self._conn.execute(
            "SELECT id,role,content,timestamp FROM memories "
            "ORDER BY timestamp DESC LIMIT ?", (n,))
        return [MemoryEntry(*row) for row in cur.fetchall()]

    def inject_context(self, user_input: str, system_prompt: str) -> str:
        """Add relevant past memories to the system prompt."""
        memories = self._retrieve(user_input, top_k=4)
        if not memories:
            return system_prompt
        snippets = "\n".join(f"- {m.content[:300]}" for m in memories)
        return system_prompt + f"\n\n[Relevant memory]\n{snippets}\n[/memory]"

    def _retrieve(self, query: str, top_k: int = 4) -> list[MemoryEntry]:
        self._ensure_encoder()
        if self._encoder:
            return self._semantic_search(query, top_k)
        return self.get_recent(top_k)

    def _semantic_search(self, query: str, top_k: int) -> list[MemoryEntry]:
        try:
            import numpy as np
            q_vec = self._encoder.encode(query)
            rows  = self._conn.execute(
                "SELECT id,role,content,timestamp,embedding FROM memories "
                "ORDER BY timestamp DESC LIMIT 200").fetchall()
            scored = []
            for row in rows:
                emb = row[4]
                if emb is None:
                    continue
                vec   = np.frombuffer(emb, dtype=np.float32)
                score = float(np.dot(q_vec, vec) /
                              (np.linalg.norm(q_vec) * np.linalg.norm(vec) + 1e-9))
                if score >= self._threshold:
                    scored.append((score, MemoryEntry(row[0], row[1], row[2], row[3])))
            scored.sort(key=lambda x: x[0], reverse=True)
            return [e for _, e in scored[:top_k]]
        except Exception:
            return self.get_recent(top_k)

    def _encode(self, text: str) -> bytes | None:
        """Encode only if encoder is already loaded — never trigger a load during store()."""
        if not self._encoder:
            return None
        try:
            import numpy as np
            return self._encoder.encode(text).astype(np.float32).tobytes()
        except Exception:
            return None

    # ── Stats ──────────────────────────────────────────────────────────────────
    def stats(self) -> dict:
        total = self._conn.execute("SELECT COUNT(*) FROM memories").fetchone()[0]
        return {
            "total_memories": total,
            "session_messages": len(self._session),
            "semantic": self._encoder is not None,
        }

    def close(self) -> None:
        self._conn.close()
