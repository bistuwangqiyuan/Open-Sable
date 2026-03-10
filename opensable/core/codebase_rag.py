"""
CodebaseRAG, Self-indexing RAG over the SableCore source code.

Exactly what GitHub Copilot does: before answering questions about the code,
it searches the codebase with vector similarity to find the relevant files
and functions, then injects that context into the LLM prompt.

Features:
- Walks opensable/ and desktop/src/ indexing all .py / .jsx / .js / .ts / .css
- Splits Python files at function/class boundaries (smart chunks)
- Incremental re-index: only re-reads files whose mtime changed
- Collection: "sablecore_code" in the same ChromaDB as other data
- search(query) → returns [{file, content, score, type}]
- Falls back to keyword grep if ChromaDB / embedding unavailable
"""

import asyncio
import hashlib
import json
import logging
import os
import re
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

# ── ChromaDB ─────────────────────────────────────────────────────────────────
try:
    import chromadb
    # Silence broken telemetry (chromadb 0.5.x changed capture() signature)
    try:
        import chromadb.telemetry.product as _ct
        _ct.ProductTelemetryClient.capture = lambda self, *a, **kw: None
    except Exception:
        pass
    _CHROMA_OK = True
except ImportError:
    _CHROMA_OK = False
    logger.info("ChromaDB not available,  CodebaseRAG will use keyword fallback")

# ── Ollama embeddings (same model as existing RAG) ────────────────────────────
try:
    import httpx

    _HTTPX_OK = True
except ImportError:
    _HTTPX_OK = False


# ─────────────────────────────────────────────────────────────────────────────
@dataclass
class CodeChunk:
    chunk_id: str
    file: str
    language: str
    chunk_type: str          # "function" | "class" | "block" | "style"
    name: str                # function/class name or ""
    content: str
    line_start: int
    line_end: int
    mtime: float = 0.0


@dataclass
class CodeSearchResult:
    file: str
    language: str
    chunk_type: str
    name: str
    content: str
    score: float
    line_start: int = 0
    line_end: int = 0


# ─────────────────────────────────────────────────────────────────────────────
_ROOT = Path(__file__).parent.parent.parent          # /home/.../SableCore_
_DATA_DIR = Path(os.environ.get("_SABLE_DATA_DIR", "data"))
_STATE_FILE = _DATA_DIR / "checkpoints" / "codebase_rag_state.json"

_INDEX_DIRS = [
    "opensable",          # all Python
    "desktop/src",        # React + CSS
]

_INCLUDE_EXTS = {".py", ".jsx", ".js", ".ts", ".tsx", ".css"}

_EXCLUDE_DIRS = {
    "__pycache__", ".git", "node_modules", "dist", "build",
    ".venv", "venv", "site-packages", ".egg-info",
}

_EMBED_MODEL = "nomic-embed-text"
_COLLECTION  = "sablecore_code"
_CHUNK_MAX   = 120    # max lines per chunk


# ─────────────────────────────────────────────────────────────────────────────
def _iter_files() -> List[Path]:
    """Yield all source files to index."""
    found = []
    for rel in _INDEX_DIRS:
        base = _ROOT / rel
        if not base.exists():
            continue
        for path in base.rglob("*"):
            if path.suffix not in _INCLUDE_EXTS:
                continue
            if any(part in _EXCLUDE_DIRS for part in path.parts):
                continue
            found.append(path)
    return found


def _chunk_python(source: str, file_path: str) -> List[CodeChunk]:
    """Split Python source at def/class boundaries."""
    lines = source.splitlines()
    chunks: List[CodeChunk] = []
    file_rel = str(Path(file_path).relative_to(_ROOT))

    # Find all top-level and first-level defs/classes
    boundary_re = re.compile(r'^(class|def|async def)\s+([\w]+)', re.MULTILINE)
    boundaries = [(m.start(), m.group(1), m.group(2)) for m in boundary_re.finditer(source)]

    if not boundaries:
        # No functions,  treat whole file as one chunk (truncate if huge)
        body = "\n".join(lines[:_CHUNK_MAX])
        cid = hashlib.md5(f"{file_rel}:0".encode()).hexdigest()[:16]
        chunks.append(CodeChunk(
            chunk_id=cid, file=file_rel, language="python",
            chunk_type="block", name="", content=body,
            line_start=1, line_end=min(len(lines), _CHUNK_MAX)
        ))
        return chunks

    # Convert byte offsets → line numbers
    byte_line = []
    pos = 0
    for ln, line in enumerate(lines, 1):
        byte_line.append((pos, ln))
        pos += len(line) + 1

    def byte_to_line(byte_off: int) -> int:
        for b, ln in reversed(byte_line):
            if b <= byte_off:
                return ln
        return 1

    for i, (bstart, kw, name) in enumerate(boundaries):
        lstart = byte_to_line(bstart)
        if i + 1 < len(boundaries):
            lend = byte_to_line(boundaries[i + 1][0]) - 1
        else:
            lend = len(lines)
        chunk_lines = lines[lstart - 1: lend]
        # Respect max chunk size
        if len(chunk_lines) > _CHUNK_MAX:
            chunk_lines = chunk_lines[:_CHUNK_MAX]
            lend = lstart + _CHUNK_MAX - 1
        body = "\n".join(chunk_lines)
        cid = hashlib.md5(f"{file_rel}:{lstart}".encode()).hexdigest()[:16]
        ctype = "class" if kw == "class" else "function"
        chunks.append(CodeChunk(
            chunk_id=cid, file=file_rel, language="python",
            chunk_type=ctype, name=name, content=body,
            line_start=lstart, line_end=lend
        ))
    return chunks


def _chunk_generic(source: str, file_path: str, language: str) -> List[CodeChunk]:
    """Chunk JS/JSX/TS/CSS by sliding window of _CHUNK_MAX lines."""
    lines = source.splitlines()
    file_rel = str(Path(file_path).relative_to(_ROOT))
    chunks = []
    step = max(_CHUNK_MAX // 2, 40)  # 50% overlap
    i = 0
    while i < len(lines):
        block = lines[i: i + _CHUNK_MAX]
        body = "\n".join(block)
        cid = hashlib.md5(f"{file_rel}:{i}".encode()).hexdigest()[:16]
        ctype = "style" if language == "css" else "block"
        chunks.append(CodeChunk(
            chunk_id=cid, file=file_rel, language=language,
            chunk_type=ctype, name="", content=body,
            line_start=i + 1, line_end=i + len(block)
        ))
        i += step
        if i >= len(lines):
            break
    return chunks


def _chunks_from_file(path: Path) -> List[CodeChunk]:
    try:
        source = path.read_text(errors="replace")
    except Exception:
        return []
    ext = path.suffix.lower()
    if ext == ".py":
        chunks = _chunk_python(source, str(path))
    elif ext == ".css":
        chunks = _chunk_generic(source, str(path), "css")
    elif ext in (".jsx", ".tsx"):
        chunks = _chunk_generic(source, str(path), "jsx")
    elif ext in (".ts",):
        chunks = _chunk_generic(source, str(path), "typescript")
    else:
        chunks = _chunk_generic(source, str(path), "javascript")
    mtime = path.stat().st_mtime
    for c in chunks:
        c.mtime = mtime
    return chunks


# ─────────────────────────────────────────────────────────────────────────────
async def _embed_one(client: "httpx.AsyncClient", text: str) -> Optional[List[float]]:
    """Try new /api/embed endpoint (Ollama ≥0.2), fall back to legacy /api/embeddings."""
    payload_new = {"model": _EMBED_MODEL, "input": text[:2000]}
    payload_old = {"model": _EMBED_MODEL, "prompt": text[:2000]}

    # ── Try new endpoint first (Ollama ≥0.2, Linux/Mac/Windows) ──────────────
    try:
        r = await client.post("http://localhost:11434/api/embed", json=payload_new)
        if r.status_code == 200:
            data = r.json()
            emb = data.get("embeddings") or data.get("embedding")
            if emb:
                return emb[0] if isinstance(emb[0], list) else emb
    except Exception:
        pass

    # ── Fallback: legacy endpoint (Ollama <0.2) ───────────────────────────────
    try:
        r = await client.post("http://localhost:11434/api/embeddings", json=payload_old)
        if r.status_code == 200:
            return r.json().get("embedding")
    except Exception:
        pass

    return None


async def _embed(texts: List[str]) -> Optional[List[List[float]]]:
    """Get embeddings from Ollama nomic-embed-text (supports all Ollama versions)."""
    if not _HTTPX_OK:
        return None
    try:
        async with httpx.AsyncClient(timeout=30) as client:
            results = []
            for text in texts:
                emb = await _embed_one(client, text)
                if emb is None:
                    return None
                results.append(emb)
            return results
    except Exception as e:
        logger.debug(f"Embedding request failed: {e}")
        return None


# ─────────────────────────────────────────────────────────────────────────────
class CodebaseRAG:
    """
    Self-indexing RAG over the SableCore codebase.

    Usage:
        rag = CodebaseRAG()
        await rag.ensure_indexed()              # called once at startup
        results = await rag.search("theme toggle button CSS")
    """

    def __init__(self):
        self._collection = None
        self._chunks: List[CodeChunk] = []      # in-memory fallback
        self._state: Dict[str, float] = {}       # file → mtime at last index
        self._ready = False
        self._indexing = False

        if _CHROMA_OK:
            try:
                persist = str(_DATA_DIR / "vectordb")
                client = chromadb.PersistentClient(path=persist)
                self._collection = client.get_or_create_collection(
                    name=_COLLECTION,
                    metadata={"hnsw:space": "cosine"},
                )
                logger.info(
                    f"📁 CodebaseRAG: ChromaDB collection '{_COLLECTION}' "
                    f"({self._collection.count()} chunks)"
                )
            except Exception as e:
                logger.warning(f"CodebaseRAG: ChromaDB init failed: {e}")

        self._load_state()

    # ── State persistence ───────────────────────────────────────────────────
    def _load_state(self):
        try:
            if _STATE_FILE.exists():
                self._state = json.loads(_STATE_FILE.read_text())
        except Exception:
            self._state = {}

    def _save_state(self):
        try:
            _STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
            _STATE_FILE.write_text(json.dumps(self._state))
        except Exception:
            pass

    # ── Indexing ────────────────────────────────────────────────────────────
    def _stale_files(self) -> List[Path]:
        """Return files that need (re-)indexing."""
        stale = []
        for path in _iter_files():
            try:
                mtime = path.stat().st_mtime
                key = str(path.relative_to(_ROOT))
                if key not in self._state or self._state[key] < mtime:
                    stale.append(path)
            except Exception:
                pass
        return stale

    async def ensure_indexed(self, force: bool = False):
        """Index / re-index stale files. Called at agent startup."""
        if self._indexing:
            return
        stale = _iter_files() if force else self._stale_files()
        if not stale:
            self._ready = True
            logger.info(f"📁 CodebaseRAG: index up to date ({self._collection.count() if self._collection else len(self._chunks)} chunks)")
            return

        self._indexing = True
        logger.info(f"📁 CodebaseRAG: indexing {len(stale)} changed files…")
        try:
            await self._index_files(stale)
        finally:
            self._indexing = False
            self._ready = True

    async def _index_files(self, files: List[Path]):
        all_chunks: List[CodeChunk] = []
        for path in files:
            chunks = _chunks_from_file(path)
            all_chunks.extend(chunks)

        if not all_chunks:
            return

        # Always keep in-memory copy for keyword fallback (cap at 8000 chunks)
        self._chunks.extend(all_chunks)
        if len(self._chunks) > 8000:
            self._chunks = self._chunks[-8000:]

        if self._collection is not None:
            # Try vector embedding
            texts = [c.content for c in all_chunks]
            embeddings = await _embed(texts)
            if embeddings:
                # Delete old chunks for these files first
                for path in files:
                    rel = str(path.relative_to(_ROOT))
                    try:
                        self._collection.delete(where={"file": rel})
                    except Exception:
                        pass
                # Upsert new chunks
                self._collection.upsert(
                    ids=[c.chunk_id for c in all_chunks],
                    documents=[c.content for c in all_chunks],
                    metadatas=[{
                        "file": c.file,
                        "language": c.language,
                        "chunk_type": c.chunk_type,
                        "name": c.name,
                        "line_start": c.line_start,
                        "line_end": c.line_end,
                    } for c in all_chunks],
                    embeddings=embeddings,
                )
                logger.info(f"📁 CodebaseRAG: upserted {len(all_chunks)} chunks to ChromaDB")
            else:
                # No embeddings → store for keyword fallback
                self._chunks.extend(all_chunks)
                logger.info(f"📁 CodebaseRAG: stored {len(all_chunks)} chunks (keyword mode, embeddings unavailable)")

        else:
            # No ChromaDB → keyword fallback
            self._chunks.extend(all_chunks)

        # Update state
        for path in files:
            rel = str(path.relative_to(_ROOT))
            try:
                self._state[rel] = path.stat().st_mtime
            except Exception:
                pass
        self._save_state()

    # ── Search ──────────────────────────────────────────────────────────────
    async def search(self, query: str, top_k: int = 5) -> List[CodeSearchResult]:
        """Semantic search over the codebase. Falls back to keyword if needed."""
        if not self._ready:
            await self.ensure_indexed()

        # Try vector search
        if self._collection is not None and self._collection.count() > 0:
            embedding = await _embed([query])
            if embedding:
                try:
                    k = min(top_k, self._collection.count())
                    res = self._collection.query(
                        query_embeddings=embedding,
                        n_results=k,
                    )
                    results = []
                    for i, doc in enumerate(res["documents"][0]):
                        meta = res["metadatas"][0][i] if res.get("metadatas") else {}
                        dist = res["distances"][0][i] if res.get("distances") else 0.0
                        score = max(0.0, 1.0 - dist)
                        results.append(CodeSearchResult(
                            file=meta.get("file", ""),
                            language=meta.get("language", ""),
                            chunk_type=meta.get("chunk_type", ""),
                            name=meta.get("name", ""),
                            content=doc,
                            score=score,
                            line_start=meta.get("line_start", 0),
                            line_end=meta.get("line_end", 0),
                        ))
                    return sorted(results, key=lambda r: r.score, reverse=True)
                except Exception as e:
                    logger.debug(f"CodebaseRAG vector search failed: {e}")

        # Keyword fallback
        return self._keyword_search(query, top_k)

    def _keyword_search(self, query: str, top_k: int) -> List[CodeSearchResult]:
        """BM25-lite keyword search over in-memory chunks."""
        words = set(re.findall(r'\w+', query.lower()))
        scored = []
        for chunk in self._chunks:
            chunk_words = set(re.findall(r'\w+', chunk.content.lower()))
            score = len(words & chunk_words) / max(len(words), 1)
            if score > 0:
                scored.append((chunk, score))
        scored.sort(key=lambda x: x[1], reverse=True)
        return [
            CodeSearchResult(
                file=c.file, language=c.language,
                chunk_type=c.chunk_type, name=c.name,
                content=c.content, score=s,
                line_start=c.line_start, line_end=c.line_end,
            )
            for c, s in scored[:top_k]
        ]

    # ── Format for LLM injection ────────────────────────────────────────────
    @staticmethod
    def format_context(results: List[CodeSearchResult], max_chars: int = 3000) -> str:
        """Format search results as a codebase context block for the LLM."""
        if not results:
            return ""
        parts = ["RELEVANT CODEBASE CONTEXT (from semantic search over source files):"]
        total = 0
        for r in results:
            header = f"\n── {r.file}"
            if r.name:
                header += f" › {r.chunk_type} `{r.name}`"
            if r.line_start:
                header += f" (lines {r.line_start}–{r.line_end})"
            header += f"  [score: {r.score:.2f}]"
            body = r.content
            # Trim very large chunks
            if len(body) > 800:
                body = body[:800] + "\n... (truncated)"
            snippet = f"{header}\n```{r.language}\n{body}\n```"
            if total + len(snippet) > max_chars:
                break
            parts.append(snippet)
            total += len(snippet)
        return "\n".join(parts)
