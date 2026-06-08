"""
rag.py — JARVIS v3 Local RAG
Index local documents and answer questions from them.
"""
from __future__ import annotations
import json, logging, os
from pathlib import Path

logger = logging.getLogger(__name__)
_EXTS = {".pdf", ".md", ".txt", ".rst", ".csv"}


class RAGEngine:
    def __init__(self, config=None) -> None:
        from memory.config_manager import get_mark_config as get_config
        cfg = config or get_config()
        self._index_path = Path(cfg.get("rag.index_path", "./data/rag_index"))
        self._chunk_size = int(cfg.get("rag.chunk_size", 500))
        self._overlap    = int(cfg.get("rag.chunk_overlap", 50))
        self._top_k      = int(cfg.get("rag.top_k", 5))
        self._index_path.mkdir(parents=True, exist_ok=True)
        self._chunks: list[dict] = []
        self._embeddings = None
        self._encoder = None
        self._load_index()
        self._try_encoder()

    def _try_encoder(self) -> None:
        try:
            from sentence_transformers import SentenceTransformer
            self._encoder = SentenceTransformer("all-MiniLM-L6-v2")
        except ImportError:
            logger.info("sentence-transformers unavailable — RAG disabled")

    def index_file(self, path: str) -> str:
        p = Path(os.path.expanduser(path))
        if not p.exists():
            return f"Not found: {path}"
        if p.suffix.lower() not in _EXTS:
            return f"Unsupported: {p.suffix}"
        text = self._read(p)
        if not text:
            return f"Could not read: {p.name}"
        self._chunks.extend(self._chunk(text, p))
        self._rebuild()
        self._save()
        return f"Indexed {p.name}"

    def index_directory(self, dir_path: str) -> str:
        d = Path(os.path.expanduser(dir_path))
        if not d.exists():
            return f"Not found: {dir_path}"
        n = 0
        for root, _, files in os.walk(d):
            for fname in files:
                if Path(fname).suffix.lower() in _EXTS:
                    self.index_file(str(Path(root) / fname))
                    n += 1
        return f"Indexed {n} files from {dir_path}"

    def _read(self, path: Path) -> str:
        try:
            if path.suffix.lower() == ".pdf":
                from actions.pdf_tools import extract_text
                return extract_text(str(path))
            return path.read_text(encoding="utf-8", errors="replace")
        except Exception as e:
            logger.warning("Read %s: %s", path, e)
            return ""

    def _chunk(self, text: str, source: Path) -> list[dict]:
        step = self._chunk_size - self._overlap
        return [{"text": text[i:i+self._chunk_size].strip(), "source": str(source), "offset": i}
                for i in range(0, len(text), step)
                if len(text[i:i+self._chunk_size].strip()) >= 50]

    def query(self, question: str, router=None) -> str:
        if not self._chunks:
            return "No documents indexed. Use index_file() or index_directory()."
        if not self._encoder:
            return "sentence-transformers not installed — RAG unavailable."
        relevant = self._retrieve(question)
        if not relevant:
            return "No relevant content found."
        context = "\n\n---\n\n".join(
            f"[{c['source'].split('/')[-1]}]\n{c['text']}" for c in relevant)
        if not router:
            return f"Context found:\n\n{context[:2000]}"
        prompt = (f"Answer using ONLY the context below. Say if the answer isn't there.\n\n"
                  f"Context:\n{context}\n\nQuestion: {question}")
        return router.chat_sync([{"role": "user", "content": prompt}])

    def _retrieve(self, query: str) -> list[dict]:
        try:
            import numpy as np
            q = self._encoder.encode(query)
            if self._embeddings is None:
                return []
            scores = (self._embeddings @ q) / (
                np.linalg.norm(self._embeddings, axis=1) * np.linalg.norm(q) + 1e-9)
            top = scores.argsort()[::-1][:self._top_k]
            return [self._chunks[i] for i in top if scores[i] > 0.2]
        except Exception:
            return []

    def _rebuild(self) -> None:
        if not self._encoder or not self._chunks:
            return
        try:
            self._embeddings = self._encoder.encode(
                [c["text"] for c in self._chunks], show_progress_bar=False)
        except Exception:
            pass

    def _save(self) -> None:
        try:
            import numpy as np
            (self._index_path / "chunks.json").write_text(json.dumps(self._chunks))
            if self._embeddings is not None:
                import numpy as np
                np.save(str(self._index_path / "embeddings.npy"), self._embeddings)
        except Exception:
            pass

    def _load_index(self) -> None:
        try:
            cf = self._index_path / "chunks.json"
            ef = self._index_path / "embeddings.npy"
            if cf.exists():
                self._chunks = json.loads(cf.read_text())
            if ef.exists():
                import numpy as np
                self._embeddings = np.load(str(ef))
        except Exception:
            pass

    def stats(self) -> dict:
        return {"chunks": len(self._chunks),
                "sources": list({c["source"] for c in self._chunks}),
                "encoder": self._encoder is not None}
