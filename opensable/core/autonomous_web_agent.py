"""
Autonomous Web Agent — WORLD FIRST
Real-time web browsing, API discovery, and autonomous information gathering.
The agent can navigate the web freely, discover new APIs, scrape data,
and build its own knowledge from the live internet without being asked.
"""
import json
import logging
import asyncio
import hashlib
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional, Dict, List, Any

logger = logging.getLogger(__name__)

# ── Data Models ───────────────────────────────────────────────────────

@dataclass
class WebTarget:
    url: str
    purpose: str
    last_visited: Optional[str] = None
    visits: int = 0
    success_rate: float = 1.0
    content_hash: Optional[str] = None
    discovered_apis: List[str] = field(default_factory=list)

@dataclass
class APIEndpoint:
    url: str
    method: str = "GET"
    discovered_at: str = ""
    description: str = ""
    parameters: Dict[str, str] = field(default_factory=dict)
    last_used: Optional[str] = None
    reliability: float = 1.0

@dataclass
class SearchResult:
    query: str
    url: str
    title: str
    snippet: str
    timestamp: str = ""
    relevance: float = 0.0

# ── Core Engine ───────────────────────────────────────────────────────

class AutonomousWebAgent:
    """
    Autonomous web navigation, search, and API discovery engine.
    Browses the web, discovers APIs, gathers real-time information,
    and builds a knowledge graph of the internet autonomously.
    """

    MAX_TARGETS = 200
    MAX_APIS = 500
    MAX_SEARCHES = 1000

    def __init__(self, data_dir: Path):
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.state_file = self.data_dir / "web_agent_state.json"

        self.targets: List[WebTarget] = []
        self.discovered_apis: List[APIEndpoint] = []
        self.search_history: List[SearchResult] = []
        self.knowledge_cache: Dict[str, Any] = {}

        # Stats
        self.total_visits = 0
        self.total_searches = 0
        self.total_apis_discovered = 0
        self.total_data_gathered_kb = 0.0
        self.active_crawls = 0

        self._load_state()

    def add_target(self, url: str, purpose: str) -> WebTarget:
        """Add a URL target for autonomous monitoring/crawling."""
        target = WebTarget(url=url, purpose=purpose)
        self.targets.append(target)
        if len(self.targets) > self.MAX_TARGETS:
            self.targets = self.targets[-self.MAX_TARGETS:]
        self._save_state()
        return target

    async def browse(self, url: str, purpose: str = "general") -> Dict[str, Any]:
        """Browse a URL and extract information."""
        try:
            import aiohttp
            async with aiohttp.ClientSession() as session:
                async with session.get(url, timeout=aiohttp.ClientTimeout(total=30),
                                       headers={"User-Agent": "Open-Sable/1.7 AutonomousWebAgent"}) as resp:
                    if resp.status == 200:
                        content = await resp.text()
                        content_hash = hashlib.sha256(content[:10000].encode()).hexdigest()[:16]
                        size_kb = len(content) / 1024

                        # Update stats
                        self.total_visits += 1
                        self.total_data_gathered_kb += size_kb

                        # Update or create target
                        existing = next((t for t in self.targets if t.url == url), None)
                        if existing:
                            existing.visits += 1
                            existing.last_visited = datetime.now(timezone.utc).isoformat()
                            existing.content_hash = content_hash
                        else:
                            self.add_target(url, purpose)

                        self._save_state()
                        return {
                            "url": url,
                            "status": resp.status,
                            "size_kb": round(size_kb, 2),
                            "content_hash": content_hash,
                            "content_preview": content[:2000],
                        }
                    return {"url": url, "status": resp.status, "error": f"HTTP {resp.status}"}
        except Exception as e:
            logger.debug(f"Browse failed for {url}: {e}")
            return {"url": url, "error": str(e)}

    async def search(self, query: str, llm=None) -> List[Dict]:
        """Search the web for information autonomously."""
        self.total_searches += 1
        results = []

        # Use DuckDuckGo Instant Answer API (no key needed)
        try:
            import aiohttp
            search_url = f"https://api.duckduckgo.com/?q={query}&format=json&no_html=1"
            async with aiohttp.ClientSession() as session:
                async with session.get(search_url, timeout=aiohttp.ClientTimeout(total=15)) as resp:
                    if resp.status == 200:
                        data = await resp.json(content_type=None)
                        if data.get("Abstract"):
                            results.append({
                                "title": data.get("Heading", query),
                                "snippet": data["Abstract"],
                                "url": data.get("AbstractURL", ""),
                                "source": "duckduckgo",
                            })
                        for topic in data.get("RelatedTopics", [])[:5]:
                            if isinstance(topic, dict) and topic.get("Text"):
                                results.append({
                                    "title": topic.get("Text", "")[:100],
                                    "snippet": topic.get("Text", ""),
                                    "url": topic.get("FirstURL", ""),
                                    "source": "duckduckgo",
                                })
        except Exception as e:
            logger.debug(f"Web search failed: {e}")

        # Record search
        for r in results:
            self.search_history.append(SearchResult(
                query=query, url=r.get("url", ""), title=r.get("title", ""),
                snippet=r.get("snippet", ""),
                timestamp=datetime.now(timezone.utc).isoformat(),
            ))

        if len(self.search_history) > self.MAX_SEARCHES:
            self.search_history = self.search_history[-self.MAX_SEARCHES:]

        self._save_state()
        return results

    async def discover_apis(self, url: str) -> List[APIEndpoint]:
        """Discover API endpoints from a URL or its documentation."""
        discovered = []
        try:
            result = await self.browse(url, "api_discovery")
            content = result.get("content_preview", "")

            # Simple heuristic: find URL patterns that look like APIs
            import re
            api_patterns = re.findall(r'(?:https?://[^\s"\'<>]+/api/[^\s"\'<>]+)', content)
            for api_url in set(api_patterns[:20]):
                ep = APIEndpoint(
                    url=api_url,
                    discovered_at=datetime.now(timezone.utc).isoformat(),
                    description=f"Discovered from {url}",
                )
                discovered.append(ep)
                self.discovered_apis.append(ep)
                self.total_apis_discovered += 1

            if len(self.discovered_apis) > self.MAX_APIS:
                self.discovered_apis = self.discovered_apis[-self.MAX_APIS:]

            self._save_state()
        except Exception as e:
            logger.debug(f"API discovery failed for {url}: {e}")

        return discovered

    async def autonomous_research(self, topic: str, llm=None) -> Dict[str, Any]:
        """Conduct autonomous research on a topic using web + LLM."""
        research = {"topic": topic, "findings": [], "sources": []}

        # Step 1: Search
        results = await self.search(topic)
        research["sources"] = [r.get("url", "") for r in results]

        # Step 2: If LLM available, synthesize findings
        if llm and results:
            snippets = "\n".join([r.get("snippet", "") for r in results[:5]])
            prompt = f"Synthesize these findings about '{topic}' into 3 key insights:\n{snippets}\nReturn as JSON list of strings."
            try:
                raw = await llm.chat_raw(prompt, max_tokens=500)
                research["findings"] = json.loads(raw) if raw.startswith("[") else [raw]
            except Exception:
                research["findings"] = [r.get("snippet", "") for r in results[:3]]
        else:
            research["findings"] = [r.get("snippet", "") for r in results[:3]]

        self.knowledge_cache[topic] = research
        self._save_state()
        return research

    def get_stats(self) -> Dict[str, Any]:
        return {
            "total_visits": self.total_visits,
            "total_searches": self.total_searches,
            "apis_discovered": self.total_apis_discovered,
            "data_gathered_kb": round(self.total_data_gathered_kb, 1),
            "active_targets": len(self.targets),
            "search_history": len(self.search_history),
            "knowledge_topics": len(self.knowledge_cache),
            "active_crawls": self.active_crawls,
        }

    def _save_state(self):
        try:
            state = {
                "targets": [asdict(t) for t in self.targets[-50:]],
                "discovered_apis": [asdict(a) for a in self.discovered_apis[-100:]],
                "search_history": [asdict(s) for s in self.search_history[-200:]],
                "total_visits": self.total_visits,
                "total_searches": self.total_searches,
                "total_apis_discovered": self.total_apis_discovered,
                "total_data_gathered_kb": self.total_data_gathered_kb,
            }
            self.state_file.write_text(json.dumps(state, indent=2))
        except Exception as e:
            logger.debug(f"Web agent save failed: {e}")

    def _load_state(self):
        try:
            if self.state_file.exists():
                state = json.loads(self.state_file.read_text())
                self.targets = [WebTarget(**t) for t in state.get("targets", [])]
                self.discovered_apis = [APIEndpoint(**a) for a in state.get("discovered_apis", [])]
                self.search_history = [SearchResult(**s) for s in state.get("search_history", [])]
                self.total_visits = state.get("total_visits", 0)
                self.total_searches = state.get("total_searches", 0)
                self.total_apis_discovered = state.get("total_apis_discovered", 0)
                self.total_data_gathered_kb = state.get("total_data_gathered_kb", 0.0)
        except Exception as e:
            logger.debug(f"Web agent load failed: {e}")
