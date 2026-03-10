"""
News Reader Skill,  fetches world news from news.zunvra.com (WorldMonitor)

Endpoints used:
  POST /api/intelligence/v1/get-country-intel-brief  ,  country OSINT briefs
  POST /api/intelligence/v1/search-gdelt-documents    ,  GDELT news search
  POST /api/conflict/v1/list-acled-events             ,  armed conflict events
  POST /api/economic/v1/get-macro-signals             ,  macroeconomic signals
  POST /api/market/v1/list-market-quotes              ,  stock market quotes
  POST /api/market/v1/list-crypto-quotes              ,  crypto prices
  GET  /api/rss-proxy?url=...                         ,  proxied RSS feeds

Results are cached to data/news_cache.json so the agent doesn't hammer
the API every tick.  Cache TTL is configurable (default 30 min).
"""

import asyncio
import json
import logging
import os
import time
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

_DATA_DIR = Path(os.environ.get("_SABLE_DATA_DIR", "data"))
_CACHE_FILE = _DATA_DIR / "news_cache.json"
_HISTORY_FILE = _DATA_DIR / "news_history.jsonl"

# Default RSS feeds the agent can pull through the rss-proxy
_DEFAULT_FEEDS = [
    {"name": "BBC World",         "url": "https://feeds.bbci.co.uk/news/world/rss.xml"},
    {"name": "Reuters World",     "url": "https://feeds.reuters.com/Reuters/worldNews"},
    {"name": "Al Jazeera",        "url": "https://www.aljazeera.com/xml/rss/all.xml"},
    {"name": "CNN Top Stories",   "url": "https://rss.cnn.com/rss/edition.rss"},
    {"name": "Hacker News",       "url": "https://hnrss.org/frontpage"},
    {"name": "ArsTechnica",       "url": "https://feeds.arstechnica.com/arstechnica/index"},
    {"name": "TechCrunch",        "url": "https://techcrunch.com/feed/"},
]


class NewsReaderSkill:
    """Reads world news from news.zunvra.com and caches results locally."""

    BASE_URL = "https://news.zunvra.com"

    def __init__(self, config):
        self.config = config
        self._ready = False
        self._cache: Dict[str, Any] = {}
        self._cache_ttl = getattr(config, "news_cache_ttl", 1800)  # 30 min
        self._session = None  # aiohttp ClientSession, created lazily

    # ── lifecycle ─────────────────────────────────────────────────────

    async def initialize(self):
        if not getattr(self.config, "news_enabled", True):
            logger.info("News reader skill disabled")
            return
        _DATA_DIR.mkdir(parents=True, exist_ok=True)
        self._load_cache()
        self._ready = True
        logger.info(
            "📰 News reader skill ready  (source: %s, cache TTL: %ss)",
            self.BASE_URL, self._cache_ttl,
        )

    async def shutdown(self):
        if self._session and not self._session.closed:
            await self._session.close()

    # ── cache management ──────────────────────────────────────────────

    def _load_cache(self):
        try:
            if _CACHE_FILE.exists():
                raw = json.loads(_CACHE_FILE.read_text("utf-8"))
                # Evict expired entries on load
                now = time.time()
                self._cache = {
                    k: v for k, v in raw.items()
                    if now - v.get("_ts", 0) < self._cache_ttl
                }
        except Exception:
            self._cache = {}

    def _save_cache(self):
        try:
            _CACHE_FILE.write_text(
                json.dumps(self._cache, ensure_ascii=False, default=str),
                encoding="utf-8",
            )
        except Exception as e:
            logger.warning("News cache save failed: %s", e)

    def _get_cached(self, key: str) -> Optional[Any]:
        entry = self._cache.get(key)
        if entry and (time.time() - entry.get("_ts", 0)) < self._cache_ttl:
            return entry.get("data")
        return None

    def _put_cache(self, key: str, data: Any):
        self._cache[key] = {"data": data, "_ts": time.time()}
        self._save_cache()

    def _append_history(self, source: str, items: List[Dict]):
        """Append digest entries to news_history.jsonl so the agent never re-reads."""
        try:
            with open(_HISTORY_FILE, "a", encoding="utf-8") as f:
                for it in items:
                    entry = {
                        "ts": time.time(),
                        "source": source,
                        "title": it.get("title", it.get("primaryTitle", "")),
                        "link": it.get("link", it.get("primaryLink", "")),
                    }
                    f.write(json.dumps(entry, ensure_ascii=False) + "\n")
        except Exception:
            pass

    # ── HTTP helpers ──────────────────────────────────────────────────

    async def _ensure_session(self):
        if self._session is None or self._session.closed:
            import aiohttp
            self._session = aiohttp.ClientSession(
                timeout=aiohttp.ClientTimeout(total=20),
                headers={"User-Agent": "SableCore/1.3 NewsReader"},
            )

    async def _post_json(self, path: str, body: Dict = None) -> Dict:
        await self._ensure_session()
        url = f"{self.BASE_URL}{path}"
        async with self._session.post(url, json=body or {}) as resp:
            resp.raise_for_status()
            return await resp.json()

    async def _get_text(self, path: str) -> str:
        await self._ensure_session()
        url = f"{self.BASE_URL}{path}"
        async with self._session.get(url) as resp:
            resp.raise_for_status()
            return await resp.text()

    # ══════════════════════════════════════════════════════════════════
    #  PUBLIC API,  called by tool bridge or autonomous loop
    # ══════════════════════════════════════════════════════════════════

    async def get_world_news(self, max_items: int = 20) -> List[Dict]:
        """Fetch headlines from multiple RSS feeds via the proxy.  Cached."""
        if not self._ready:
            return [{"title": "(news reader not initialised)"}]

        cached = self._get_cached("world_news")
        if cached:
            return cached[:max_items]

        all_items: List[Dict] = []
        for feed in _DEFAULT_FEEDS:
            try:
                xml_text = await self._get_text(
                    f"/api/rss-proxy?url={feed['url']}"
                )
                items = self._parse_rss(xml_text, feed["name"])
                all_items.extend(items)
            except Exception as e:
                logger.debug("RSS fetch failed for %s: %s", feed["name"], e)

        # Sort by pubDate desc, deduplicate by title similarity
        all_items.sort(key=lambda x: x.get("pubDate", ""), reverse=True)
        deduped = self._deduplicate(all_items)[:60]

        self._put_cache("world_news", deduped)
        self._append_history("rss", deduped[:max_items])
        return deduped[:max_items]

    async def search_news(self, query: str, max_items: int = 15) -> List[Dict]:
        """Search GDELT for news matching a query.  Cached per query."""
        if not self._ready:
            return []

        cache_key = f"search:{query.lower().strip()}"
        cached = self._get_cached(cache_key)
        if cached:
            return cached[:max_items]

        try:
            data = await self._post_json(
                "/api/intelligence/v1/search-gdelt-documents",
                {"query": query, "maxRecords": max_items},
            )
            articles = data.get("articles") or data.get("documents") or []
            result = [
                {
                    "title": a.get("title", ""),
                    "link": a.get("url", a.get("link", "")),
                    "source": a.get("source", a.get("domain", "")),
                    "pubDate": a.get("dateAdded", a.get("publishDate", "")),
                    "tone": a.get("tone", None),
                }
                for a in articles[:max_items]
            ]
            self._put_cache(cache_key, result)
            self._append_history("gdelt", result)
            return result
        except Exception as e:
            logger.warning("GDELT search failed: %s", e)
            return []

    async def get_country_brief(self, country_code: str) -> Dict:
        """Get an intelligence brief for a country (e.g. 'US', 'CN', 'UA')."""
        if not self._ready:
            return {"error": "not initialised"}

        cache_key = f"brief:{country_code.upper()}"
        cached = self._get_cached(cache_key)
        if cached:
            return cached

        try:
            data = await self._post_json(
                "/api/intelligence/v1/get-country-intel-brief",
                {"countryCode": country_code.upper()},
            )
            self._put_cache(cache_key, data)
            return data
        except Exception as e:
            logger.warning("Country brief failed for %s: %s", country_code, e)
            return {"error": str(e)}

    async def get_conflicts(self, max_items: int = 20) -> List[Dict]:
        """Get recent armed conflict events (ACLED)."""
        if not self._ready:
            return []

        cached = self._get_cached("conflicts")
        if cached:
            return cached[:max_items]

        try:
            data = await self._post_json(
                "/api/conflict/v1/list-acled-events", {}
            )
            events = data.get("events") or data.get("items") or []
            result = [
                {
                    "type": ev.get("event_type", ev.get("type", "")),
                    "country": ev.get("country", ""),
                    "location": ev.get("location", ""),
                    "date": ev.get("event_date", ev.get("date", "")),
                    "fatalities": ev.get("fatalities", 0),
                    "notes": (ev.get("notes", "") or "")[:200],
                }
                for ev in events[:max_items]
            ]
            self._put_cache("conflicts", result)
            return result
        except Exception as e:
            logger.warning("Conflict fetch failed: %s", e)
            return []

    async def get_macro_signals(self) -> Dict:
        """Get macroeconomic signals (GDP, inflation, rates, etc.)."""
        if not self._ready:
            return {}

        cached = self._get_cached("macro")
        if cached:
            return cached

        try:
            data = await self._post_json(
                "/api/economic/v1/get-macro-signals", {}
            )
            self._put_cache("macro", data)
            return data
        except Exception as e:
            logger.warning("Macro signals failed: %s", e)
            return {}

    async def get_market_quotes(self, symbols: List[str] = None) -> List[Dict]:
        """Get stock market quotes."""
        if not self._ready:
            return []

        syms = symbols or ["SPY", "QQQ", "DIA", "AAPL", "MSFT"]
        cache_key = f"market:{','.join(syms)}"
        cached = self._get_cached(cache_key)
        if cached:
            return cached

        try:
            data = await self._post_json(
                "/api/market/v1/list-market-quotes",
                {"symbols": syms},
            )
            quotes = data.get("quotes") or data.get("items") or []
            self._put_cache(cache_key, quotes)
            return quotes
        except Exception as e:
            logger.warning("Market quotes failed: %s", e)
            return []

    async def get_crypto_quotes(self, symbols: List[str] = None) -> List[Dict]:
        """Get cryptocurrency quotes."""
        if not self._ready:
            return []

        syms = symbols or ["bitcoin", "ethereum", "solana"]
        cache_key = f"crypto:{','.join(syms)}"
        cached = self._get_cached(cache_key)
        if cached:
            return cached

        try:
            data = await self._post_json(
                "/api/market/v1/list-crypto-quotes",
                {"ids": syms},
            )
            quotes = data.get("quotes") or data.get("items") or []
            self._put_cache(cache_key, quotes)
            return quotes
        except Exception as e:
            logger.warning("Crypto quotes failed: %s", e)
            return []

    async def get_news_digest(self) -> str:
        """
        Produce a plain-text digest combining top headlines, conflicts, and macro
        signals.  Ideal for the autonomous loop to read once per cycle.
        """
        parts: List[str] = []

        # Headlines
        headlines = await self.get_world_news(max_items=10)
        if headlines:
            parts.append("── TOP HEADLINES ──")
            for i, h in enumerate(headlines, 1):
                parts.append(f"  {i}. [{h.get('source','')}] {h.get('title','')}")

        # Conflicts
        conflicts = await self.get_conflicts(max_items=5)
        if conflicts:
            parts.append("\n── CONFLICT EVENTS ──")
            for c in conflicts:
                parts.append(
                    f"  • {c.get('country','')},  {c.get('type','')}: "
                    f"{c.get('notes','')[:100]}"
                )

        # Macro
        macro = await self.get_macro_signals()
        if macro and not macro.get("error"):
            parts.append("\n── MACRO SIGNALS ──")
            # Flatten whatever the endpoint returns
            for k, v in list(macro.items())[:10]:
                if k.startswith("_"):
                    continue
                parts.append(f"  {k}: {v}")

        if not parts:
            return "(no news available)"

        return "\n".join(parts)

    # ── RSS parsing ───────────────────────────────────────────────────

    @staticmethod
    def _parse_rss(xml_text: str, source_name: str) -> List[Dict]:
        items: List[Dict] = []
        try:
            root = ET.fromstring(xml_text)
            # RSS 2.0
            for item in root.findall(".//item"):
                title = (item.findtext("title") or "").strip()
                link = (item.findtext("link") or "").strip()
                pub = (item.findtext("pubDate") or "").strip()
                desc = (item.findtext("description") or "").strip()
                if title:
                    items.append({
                        "title": title,
                        "link": link,
                        "pubDate": pub,
                        "source": source_name,
                        "description": desc[:300] if desc else "",
                    })
            # Atom fallback
            if not items:
                ns = {"atom": "http://www.w3.org/2005/Atom"}
                for entry in root.findall(".//atom:entry", ns):
                    title = (entry.findtext("atom:title", namespaces=ns) or "").strip()
                    link_el = entry.find("atom:link", ns)
                    link = link_el.get("href", "") if link_el is not None else ""
                    pub = (entry.findtext("atom:published", namespaces=ns)
                           or entry.findtext("atom:updated", namespaces=ns) or "")
                    if title:
                        items.append({
                            "title": title, "link": link,
                            "pubDate": pub, "source": source_name,
                        })
        except ET.ParseError:
            pass
        return items

    @staticmethod
    def _deduplicate(items: List[Dict], threshold: float = 0.6) -> List[Dict]:
        """Simple word-overlap dedup."""
        seen_sets: List[set] = []
        result: List[Dict] = []
        for it in items:
            words = set(it.get("title", "").lower().split())
            if not words:
                continue
            dup = False
            for s in seen_sets:
                overlap = len(words & s) / max(len(words | s), 1)
                if overlap > threshold:
                    dup = True
                    break
            if not dup:
                seen_sets.append(words)
                result.append(it)
        return result
