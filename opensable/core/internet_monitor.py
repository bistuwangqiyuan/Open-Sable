"""
Persistent Internet Monitor,  WORLD FIRST
24/7 persistent monitoring of the internet: news feeds, social media,
market data, research papers, and emergent trends.
The agent never sleeps,  it watches the world continuously.
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
class MonitoredSource:
    id: str
    name: str
    url: str
    category: str  # news, social, market, research, custom
    check_interval_seconds: int = 300
    last_checked: Optional[str] = None
    total_checks: int = 0
    total_alerts: int = 0
    active: bool = True

@dataclass
class Alert:
    id: str
    source_id: str
    category: str
    title: str
    summary: str
    timestamp: str
    severity: str = "info"  # info, warning, critical
    url: Optional[str] = None
    acknowledged: bool = False

@dataclass
class Trend:
    topic: str
    first_seen: str
    mentions: int = 1
    sources: List[str] = field(default_factory=list)
    sentiment: float = 0.0  # -1 to 1
    velocity: float = 0.0  # rate of growth

# ── Core Monitor ──────────────────────────────────────────────────────

class InternetMonitor:
    """
    Persistent internet monitoring engine.
    Watches news, social media, markets, and research 24/7.
    Detects trends, generates alerts, tracks global events.
    """

    DEFAULT_SOURCES = [
        {"name": "HackerNews", "url": "https://hacker-news.firebaseio.com/v0/topstories.json", "category": "news"},
        {"name": "Reddit Tech", "url": "https://www.reddit.com/r/technology/.json", "category": "social"},
        {"name": "ArXiv CS.AI", "url": "http://export.arxiv.org/api/query?search_query=cat:cs.AI&max_results=10&sortBy=submittedDate", "category": "research"},
    ]
    MAX_ALERTS = 500
    MAX_TRENDS = 200

    def __init__(self, data_dir: Path):
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.state_file = self.data_dir / "internet_monitor_state.json"

        self.sources: List[MonitoredSource] = []
        self.alerts: List[Alert] = []
        self.trends: List[Trend] = []
        self.total_checks = 0
        self.total_alerts_generated = 0
        self.total_trends_detected = 0
        self.is_monitoring = False
        self._monitor_task: Optional[asyncio.Task] = None

        self._load_state()

        # Initialize default sources if none exist
        if not self.sources:
            for src in self.DEFAULT_SOURCES:
                sid = hashlib.sha256(src["url"].encode()).hexdigest()[:10]
                self.sources.append(MonitoredSource(id=sid, **src))
            self._save_state()

    def add_source(self, name: str, url: str, category: str = "custom", interval: int = 300) -> MonitoredSource:
        """Add a new monitored source."""
        sid = hashlib.sha256(f"{name}_{url}".encode()).hexdigest()[:10]
        source = MonitoredSource(id=sid, name=name, url=url, category=category, check_interval_seconds=interval)
        self.sources.append(source)
        self._save_state()
        return source

    def remove_source(self, source_id: str) -> bool:
        """Remove a monitored source."""
        before = len(self.sources)
        self.sources = [s for s in self.sources if s.id != source_id]
        if len(self.sources) < before:
            self._save_state()
            return True
        return False

    async def check_source(self, source: MonitoredSource) -> List[Dict[str, Any]]:
        """Check a single source for new content."""
        results = []
        try:
            import aiohttp
            async with aiohttp.ClientSession() as session:
                async with session.get(source.url, timeout=aiohttp.ClientTimeout(total=15)) as resp:
                    if resp.status == 200:
                        content_type = resp.headers.get("content-type", "")
                        if "json" in content_type:
                            data = await resp.json()
                            results.append({"type": "json", "data": data, "size": len(str(data))})
                        elif "xml" in content_type or "atom" in content_type:
                            text = await resp.text()
                            results.append({"type": "xml", "data": text[:2000], "size": len(text)})
                        else:
                            text = await resp.text()
                            results.append({"type": "text", "data": text[:2000], "size": len(text)})

            source.total_checks += 1
            source.last_checked = datetime.now(timezone.utc).isoformat()
            self.total_checks += 1

        except Exception as e:
            logger.debug(f"Monitor check failed for {source.name}: {e}")
            results.append({"type": "error", "error": str(e)})

        return results

    async def scan_all(self, llm=None) -> Dict[str, Any]:
        """Scan all active sources and generate alerts."""
        scan_results = {}
        new_alerts = 0

        for source in self.sources:
            if not source.active:
                continue
            data = await self.check_source(source)
            scan_results[source.name] = {"category": source.category, "results": len(data)}

            # Generate alerts from LLM analysis if available
            if llm and data and data[0].get("type") != "error":
                try:
                    content = str(data[0].get("data", ""))[:1500]
                    prompt = (
                        f"Analyze this {source.category} feed from {source.name}. "
                        f"Identify any important, trending, or critical items. "
                        f"Reply with a JSON array of objects with 'title', 'summary', 'severity' (info/warning/critical). "
                        f"Max 3 items. If nothing notable, reply with empty array [].\n\n{content}"
                    )
                    analysis = await llm.chat_raw(prompt, max_tokens=500)
                    try:
                        items = json.loads(analysis.strip())
                        if isinstance(items, list):
                            for item in items[:3]:
                                alert_id = hashlib.sha256(f"{source.id}_{item.get('title', '')}".encode()).hexdigest()[:10]
                                alert = Alert(
                                    id=alert_id, source_id=source.id, category=source.category,
                                    title=item.get("title", "Unknown"),
                                    summary=item.get("summary", ""),
                                    timestamp=datetime.now(timezone.utc).isoformat(),
                                    severity=item.get("severity", "info"),
                                    url=source.url,
                                )
                                self.alerts.append(alert)
                                new_alerts += 1
                                self.total_alerts_generated += 1
                    except json.JSONDecodeError:
                        pass
                except Exception as e:
                    logger.debug(f"Alert generation failed: {e}")

        # Trim alerts
        if len(self.alerts) > self.MAX_ALERTS:
            self.alerts = self.alerts[-self.MAX_ALERTS:]

        self._save_state()
        return {"sources_scanned": len(scan_results), "new_alerts": new_alerts, "details": scan_results}

    def detect_trend(self, topic: str, source: str, sentiment: float = 0.0):
        """Record a trending topic."""
        existing = next((t for t in self.trends if t.topic.lower() == topic.lower()), None)
        if existing:
            existing.mentions += 1
            if source not in existing.sources:
                existing.sources.append(source)
            existing.sentiment = (existing.sentiment + sentiment) / 2
        else:
            trend = Trend(
                topic=topic, first_seen=datetime.now(timezone.utc).isoformat(),
                sources=[source], sentiment=sentiment,
            )
            self.trends.append(trend)
            self.total_trends_detected += 1
            if len(self.trends) > self.MAX_TRENDS:
                self.trends = self.trends[-self.MAX_TRENDS:]
        self._save_state()

    async def start_monitoring(self, llm=None, interval: int = 300):
        """Start background monitoring loop."""
        if self.is_monitoring:
            return
        self.is_monitoring = True

        async def _loop():
            while self.is_monitoring:
                try:
                    await self.scan_all(llm)
                except Exception as e:
                    logger.debug(f"Monitor loop error: {e}")
                await asyncio.sleep(interval)

        self._monitor_task = asyncio.create_task(_loop())
        logger.info(f"Internet monitoring started (interval: {interval}s)")

    def stop_monitoring(self):
        """Stop background monitoring."""
        self.is_monitoring = False
        if self._monitor_task:
            self._monitor_task.cancel()
            self._monitor_task = None

    def get_stats(self) -> Dict[str, Any]:
        return {
            "active_sources": sum(1 for s in self.sources if s.active),
            "total_sources": len(self.sources),
            "total_checks": self.total_checks,
            "total_alerts": self.total_alerts_generated,
            "unacknowledged_alerts": sum(1 for a in self.alerts if not a.acknowledged),
            "trends_detected": self.total_trends_detected,
            "is_monitoring": self.is_monitoring,
            "categories": list(set(s.category for s in self.sources)),
        }

    def _save_state(self):
        try:
            state = {
                "sources": [asdict(s) for s in self.sources],
                "alerts": [asdict(a) for a in self.alerts[-100:]],
                "trends": [asdict(t) for t in self.trends[-50:]],
                "total_checks": self.total_checks,
                "total_alerts_generated": self.total_alerts_generated,
                "total_trends_detected": self.total_trends_detected,
            }
            self.state_file.write_text(json.dumps(state, indent=2))
        except Exception as e:
            logger.debug(f"InternetMonitor save failed: {e}")

    def _load_state(self):
        try:
            if self.state_file.exists():
                state = json.loads(self.state_file.read_text())
                self.sources = [MonitoredSource(**s) for s in state.get("sources", [])]
                self.alerts = [Alert(**a) for a in state.get("alerts", [])]
                self.trends = [Trend(**t) for t in state.get("trends", [])]
                self.total_checks = state.get("total_checks", 0)
                self.total_alerts_generated = state.get("total_alerts_generated", 0)
                self.total_trends_detected = state.get("total_trends_detected", 0)
        except Exception as e:
            logger.debug(f"InternetMonitor load failed: {e}")
